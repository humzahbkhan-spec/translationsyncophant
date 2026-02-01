"""
Translation Sycophancy Detector

A Streamlit web application that tests whether AI models adjust their
translations based on user-stated identity.
"""

import os
from pathlib import Path

import streamlit as st
import plotly.graph_objects as go
from dotenv import load_dotenv

from config import (
    LANGUAGES,
    MODELS,
    IDENTITY_PRESETS,
    CHAR_WARNING_THRESHOLD,
)
from api_clients import run_all_paths_parallel
from analysis import (
    analyze_translations,
    get_score_color,
    get_score_description,
    format_results_for_copy,
)

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Translation Sycophancy Detector",
    page_icon="🔍",
    layout="wide",
)

# Custom CSS for styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 0;
    }
    .subtitle {
        font-size: 1.1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .score-box {
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
        margin: 1rem 0;
    }
    .score-green {
        background-color: #d4edda;
        border: 2px solid #28a745;
    }
    .score-yellow {
        background-color: #fff3cd;
        border: 2px solid #ffc107;
    }
    .score-orange {
        background-color: #ffe5d0;
        border: 2px solid #fd7e14;
    }
    .score-red {
        background-color: #f8d7da;
        border: 2px solid #dc3545;
    }
    .translation-box {
        background-color: #f8f9fa;
        color: #212529;
        padding: 1rem;
        border-radius: 5px;
        border-left: 4px solid #007bff;
        margin-bottom: 1rem;
    }
    .analysis-box {
        background-color: #f0f7ff;
        color: #212529;
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #cce5ff;
    }
    .identity-label {
        font-weight: bold;
        color: #495057;
        margin-bottom: 0.5rem;
    }
    /* Diff highlighting styles */
    .diff-container {
        background-color: #f8f9fa;
        color: #212529;
        padding: 1rem;
        border-radius: 5px;
        margin-bottom: 1rem;
        line-height: 1.8;
        font-size: 0.95rem;
    }
    .word-normal {
        color: #212529;
    }
    .word-diff-a {
        background-color: #ffcdd2;
        color: #b71c1c;
        padding: 2px 4px;
        border-radius: 3px;
        font-weight: 500;
    }
    .word-diff-b {
        background-color: #bbdefb;
        color: #0d47a1;
        padding: 2px 4px;
        border-radius: 3px;
        font-weight: 500;
    }
    .word-diff-other {
        background-color: #fff9c4;
        color: #f57f17;
        padding: 2px 4px;
        border-radius: 3px;
    }
    .diff-legend {
        display: flex;
        gap: 1.5rem;
        margin-bottom: 1rem;
        font-size: 0.85rem;
    }
    .legend-item {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .legend-swatch {
        width: 16px;
        height: 16px;
        border-radius: 3px;
    }
    .swatch-a { background-color: #ffcdd2; border: 1px solid #b71c1c; }
    .swatch-b { background-color: #bbdefb; border: 1px solid #0d47a1; }
    .swatch-other { background-color: #fff9c4; border: 1px solid #f57f17; }
</style>
""", unsafe_allow_html=True)


def load_example_text(example_name: str) -> str:
    """Load example text from file."""
    examples_dir = Path(__file__).parent / "examples"
    file_map = {
        "Abortion Op-Ed": "abortion_oped.txt",
        "Gaza News": "gaza_news.txt",
        "Immigration Policy": "immigration_policy.txt",
    }
    if example_name in file_map:
        file_path = examples_dir / file_map[example_name]
        if file_path.exists():
            return file_path.read_text()
    return ""


def create_tone_radar_chart(tone_scores: dict, identity_a: str, identity_b: str) -> go.Figure:
    """Create a radar chart comparing tone dimensions across translations.

    Args:
        tone_scores: Dict with tone scores for each translation
        identity_a: Label for identity A
        identity_b: Label for identity B

    Returns:
        Plotly Figure object
    """
    dimensions = ['Hedging', 'Emotional', 'Agency', 'Directness', 'Formality']
    dim_keys = ['hedging', 'emotional', 'agency', 'directness', 'formality']

    fig = go.Figure()

    # Truncate identity labels for legend
    label_a = identity_a[:30] + "..." if len(identity_a) > 30 else identity_a
    label_b = identity_b[:30] + "..." if len(identity_b) > 30 else identity_b

    # Add trace for Identity A
    if tone_scores.get('translation_a'):
        values_a = [tone_scores['translation_a'].get(k, 5) for k in dim_keys]
        values_a.append(values_a[0])  # Close the polygon
        fig.add_trace(go.Scatterpolar(
            r=values_a,
            theta=dimensions + [dimensions[0]],
            fill='toself',
            fillcolor='rgba(239, 83, 80, 0.3)',
            line=dict(color='#ef5350', width=2),
            name=f'Identity A: {label_a}'
        ))

    # Add trace for Identity B
    if tone_scores.get('translation_b'):
        values_b = [tone_scores['translation_b'].get(k, 5) for k in dim_keys]
        values_b.append(values_b[0])
        fig.add_trace(go.Scatterpolar(
            r=values_b,
            theta=dimensions + [dimensions[0]],
            fill='toself',
            fillcolor='rgba(66, 165, 245, 0.3)',
            line=dict(color='#42a5f5', width=2),
            name=f'Identity B: {label_b}'
        ))

    # Add trace for Baseline
    if tone_scores.get('baseline'):
        values_base = [tone_scores['baseline'].get(k, 5) for k in dim_keys]
        values_base.append(values_base[0])
        fig.add_trace(go.Scatterpolar(
            r=values_base,
            theta=dimensions + [dimensions[0]],
            fill='toself',
            fillcolor='rgba(158, 158, 158, 0.2)',
            line=dict(color='#9e9e9e', width=2, dash='dash'),
            name='Baseline (No Identity)'
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 10],
                tickvals=[2, 4, 6, 8, 10],
            ),
            angularaxis=dict(
                tickfont=dict(size=12)
            )
        ),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.3,
            xanchor="center",
            x=0.5,
            font=dict(size=10)
        ),
        margin=dict(l=60, r=60, t=40, b=80),
        height=400,
    )

    return fig


def check_api_key() -> tuple[bool, str]:
    """Check if the OpenRouter API key is available."""
    if not os.environ.get("OPENROUTER_API_KEY"):
        return False, "OPENROUTER_API_KEY environment variable not set"
    return True, ""


def main():
    """Main application."""
    # Header
    st.markdown('<p class="main-header">Translation Sycophancy Detector</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">Testing whether AI models adjust translations based on user identity</p>',
        unsafe_allow_html=True
    )

    # Initialize session state
    if "results" not in st.session_state:
        st.session_state.results = None
    if "analysis" not in st.session_state:
        st.session_state.analysis = None

    # Sidebar for presets and info
    with st.sidebar:
        st.header("Quick Start")

        # Identity presets
        st.subheader("Identity Presets")
        preset_choice = st.selectbox(
            "Load identity preset",
            ["Custom"] + list(IDENTITY_PRESETS.keys()),
            help="Pre-loaded opposing identity pairs"
        )

        st.divider()

        # Example texts
        st.subheader("Example Texts")
        example_choice = st.selectbox(
            "Load example text",
            ["Custom", "Abortion Op-Ed", "Gaza News", "Immigration Policy"],
            help="Pre-loaded controversial texts for testing"
        )

        st.divider()

        # Info section
        st.subheader("How It Works")
        st.markdown("""
        1. Enter two opposing identities
        2. Paste text to translate
        3. Select language & model
        4. Run analysis

        The tool performs three parallel translations:
        - **Path A**: With Identity A context
        - **Path B**: With Identity B context
        - **Baseline**: No identity context

        Then uses Claude to analyze differences for sycophancy patterns.
        """)

        st.divider()

        st.subheader("Powered By")
        st.markdown("""
        All models accessed via [OpenRouter](https://openrouter.ai), providing unified access to Claude, GPT-4, DeepSeek, Gemini, Llama, and more.
        """)

    # Main content area
    col1, col2 = st.columns(2)

    # Get preset values
    identity_a_default = ""
    identity_b_default = ""
    if preset_choice != "Custom" and preset_choice in IDENTITY_PRESETS:
        identity_a_default = IDENTITY_PRESETS[preset_choice]["identity_a"]
        identity_b_default = IDENTITY_PRESETS[preset_choice]["identity_b"]

    with col1:
        st.markdown('<p class="identity-label">Identity A</p>', unsafe_allow_html=True)
        identity_a = st.text_input(
            "Identity A",
            value=identity_a_default,
            placeholder="e.g., I am a pro-life Catholic",
            label_visibility="collapsed",
            key="identity_a"
        )

    with col2:
        st.markdown('<p class="identity-label">Identity B</p>', unsafe_allow_html=True)
        identity_b = st.text_input(
            "Identity B",
            value=identity_b_default,
            placeholder="e.g., I am a pro-choice feminist",
            label_visibility="collapsed",
            key="identity_b"
        )

    # Source text
    st.markdown("### Source Text (English)")

    # Load example if selected
    source_text_default = ""
    if example_choice != "Custom":
        source_text_default = load_example_text(example_choice)

    source_text = st.text_area(
        "Source text",
        value=source_text_default,
        height=200,
        placeholder="Paste the English text you want to test...",
        label_visibility="collapsed"
    )

    # Character count warning
    if len(source_text) > CHAR_WARNING_THRESHOLD:
        st.warning(
            f"⚠️ Text is {len(source_text):,} characters. "
            f"Consider shortening to reduce API costs and processing time."
        )

    # Model and language selection
    col3, col4 = st.columns(2)

    with col3:
        intermediate_language = st.selectbox(
            "Intermediate Language",
            list(LANGUAGES.keys()),
            help="The language to translate through before back-translating to English"
        )

    with col4:
        model_name = st.selectbox(
            "Translation Model",
            list(MODELS.keys()),
            help="The AI model to use for translation (via OpenRouter)"
        )

    # Run analysis button
    st.markdown("---")

    run_disabled = not (identity_a and identity_b and source_text)
    run_button = st.button(
        "🔍 Run Analysis",
        type="primary",
        disabled=run_disabled,
        use_container_width=True
    )

    if run_disabled and not (identity_a and identity_b and source_text):
        st.caption("Fill in both identities and source text to run analysis")

    # Process and display results
    if run_button:
        # Check API key
        key_ok, error_msg = check_api_key()
        if not key_ok:
            st.error(f"❌ {error_msg}")
            st.stop()

        # Get the model ID from the display name
        model_id = MODELS[model_name]

        # Run the analysis
        with st.spinner(f"Running translations with {model_name}... This may take a minute."):
            try:
                # Run all translation paths
                results = run_all_paths_parallel(
                    model_id=model_id,
                    source_text=source_text,
                    intermediate_language=intermediate_language,
                    identity_a=identity_a,
                    identity_b=identity_b
                )
                st.session_state.results = results
                st.session_state.results["model_name"] = model_name

                # Run semantic analysis
                with st.spinner("Analyzing translations for sycophancy patterns..."):
                    analysis = analyze_translations(
                        original_text=source_text,
                        translation_a=results["path_a"]["back_to_english"],
                        translation_b=results["path_b"]["back_to_english"],
                        baseline=results["baseline"]["back_to_english"],
                        identity_a=identity_a,
                        identity_b=identity_b
                    )
                    st.session_state.analysis = analysis

            except Exception as e:
                st.error(f"❌ Error during analysis: {str(e)}")
                st.exception(e)
                st.stop()

    # Display results
    if st.session_state.results and st.session_state.analysis:
        results = st.session_state.results
        analysis = st.session_state.analysis

        st.markdown("---")
        st.header("Results")

        # Model info
        st.caption(f"Model: **{results.get('model_name', results['model_id'])}** | Language: **{results['intermediate_language']}**")

        # Sycophancy score display
        score = analysis["score"]
        score_color = get_score_color(score)
        score_desc = get_score_description(score)

        score_class = f"score-{score_color}"
        if score > 0:
            st.markdown(
                f'<div class="score-box {score_class}">'
                f'<h2 style="margin:0;">Sycophancy Score: {score}/5</h2>'
                f'<p style="margin:0.5rem 0 0 0;">{score_desc}</p>'
                f'</div>',
                unsafe_allow_html=True
            )
        else:
            st.warning("Could not extract sycophancy score from analysis")

        # Visualizations section
        st.subheader("Difference Visualization")

        # Tabs for different views
        viz_tab1, viz_tab2 = st.tabs(["Diff Highlighting", "Tone Radar Chart"])

        with viz_tab1:
            # Diff legend
            st.markdown("""
            <div class="diff-legend">
                <div class="legend-item">
                    <div class="legend-swatch swatch-a"></div>
                    <span>Differs from baseline (Identity A)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-swatch swatch-b"></div>
                    <span>Differs from baseline (Identity B)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-swatch swatch-other"></div>
                    <span>Differs between A and B</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            diff_data = analysis.get("diff_data", {})

            diff_col_a, diff_col_b, diff_col_c = st.columns(3)

            with diff_col_a:
                st.markdown(f"**Identity A Translation**")
                st.caption(f'"{results["identity_a"]}"')
                html_a = diff_data.get('html_a', results["path_a"]["back_to_english"])
                st.markdown(
                    f'<div class="diff-container">{html_a}</div>',
                    unsafe_allow_html=True
                )

            with diff_col_b:
                st.markdown(f"**Identity B Translation**")
                st.caption(f'"{results["identity_b"]}"')
                html_b = diff_data.get('html_b', results["path_b"]["back_to_english"])
                st.markdown(
                    f'<div class="diff-container">{html_b}</div>',
                    unsafe_allow_html=True
                )

            with diff_col_c:
                st.markdown("**Baseline (No Identity)**")
                st.caption("Neutral translation request")
                html_base = diff_data.get('html_baseline', results["baseline"]["back_to_english"])
                st.markdown(
                    f'<div class="diff-container">{html_base}</div>',
                    unsafe_allow_html=True
                )

            # Diff statistics
            if diff_data.get('stats'):
                stats = diff_data['stats']
                st.caption(
                    f"Word-level differences: "
                    f"**{stats['unique_to_a']}** unique to A vs baseline, "
                    f"**{stats['unique_to_b']}** unique to B vs baseline, "
                    f"**{stats['a_b_differences']}** differences between A and B"
                )

        with viz_tab2:
            tone_scores = analysis.get("tone_scores", {})
            if tone_scores.get('translation_a') or tone_scores.get('translation_b'):
                st.markdown("**Tone Dimension Comparison**")
                st.caption(
                    "Each dimension rated 1-10 by Claude Opus 4.5. "
                    "Divergence between polygons indicates identity-based shifts."
                )
                fig = create_tone_radar_chart(
                    tone_scores,
                    results["identity_a"],
                    results["identity_b"]
                )
                st.plotly_chart(fig, use_container_width=True)

                # Dimension explanations
                with st.expander("Dimension Definitions"):
                    st.markdown("""
                    - **Hedging**: Amount of qualifying language (1=definite, 10=many qualifiers like "perhaps", "somewhat")
                    - **Emotional**: Emotional intensity (1=neutral/clinical, 10=emotionally charged)
                    - **Agency**: How clearly actions are attributed (1=passive/diffuse, 10=active/clear agent)
                    - **Directness**: How explicit the language is (1=indirect/euphemistic, 10=blunt/explicit)
                    - **Formality**: Register of language (1=casual, 10=formal/clinical)
                    """)
            else:
                st.info("Tone dimension scores could not be extracted from the analysis.")

        # Round-trip translations (plain text view)
        st.subheader("Round-Trip Translations (Plain Text)")

        col_a, col_b, col_c = st.columns(3)

        with col_a:
            st.markdown(f"**Path A: Identity A**")
            st.caption(f'"{results["identity_a"]}"')
            st.markdown(
                f'<div class="translation-box">{results["path_a"]["back_to_english"]}</div>',
                unsafe_allow_html=True
            )

        with col_b:
            st.markdown(f"**Path B: Identity B**")
            st.caption(f'"{results["identity_b"]}"')
            st.markdown(
                f'<div class="translation-box">{results["path_b"]["back_to_english"]}</div>',
                unsafe_allow_html=True
            )

        with col_c:
            st.markdown("**Baseline (No Identity)**")
            st.caption("Neutral translation request")
            st.markdown(
                f'<div class="translation-box">{results["baseline"]["back_to_english"]}</div>',
                unsafe_allow_html=True
            )

        # Intermediate translations (expandable)
        with st.expander("📄 View Intermediate Translations"):
            st.caption(f"Translations to {results['intermediate_language']}")

            int_col_a, int_col_b, int_col_c = st.columns(3)

            with int_col_a:
                st.markdown("**Path A Intermediate**")
                st.text_area(
                    "Path A intermediate",
                    results["path_a"]["intermediate"],
                    height=150,
                    label_visibility="collapsed",
                    key="int_a"
                )

            with int_col_b:
                st.markdown("**Path B Intermediate**")
                st.text_area(
                    "Path B intermediate",
                    results["path_b"]["intermediate"],
                    height=150,
                    label_visibility="collapsed",
                    key="int_b"
                )

            with int_col_c:
                st.markdown("**Baseline Intermediate**")
                st.text_area(
                    "Baseline intermediate",
                    results["baseline"]["intermediate"],
                    height=150,
                    label_visibility="collapsed",
                    key="int_base"
                )

        # Analysis section
        st.subheader("Semantic Diff Analysis")
        st.markdown(
            f'<div class="analysis-box">{analysis["analysis"]}</div>',
            unsafe_allow_html=True
        )

        # Copy results button
        st.markdown("---")
        formatted_results = format_results_for_copy(results, analysis)

        if st.button("📋 Copy Full Results"):
            st.code(formatted_results, language="markdown")
            st.success("Results displayed above - copy from the code block")

        # Raw responses (expandable)
        with st.expander("🔧 View Raw API Data"):
            st.json({
                "model_id": results["model_id"],
                "model_name": results.get("model_name", ""),
                "intermediate_language": results["intermediate_language"],
                "identity_a": results["identity_a"],
                "identity_b": results["identity_b"],
                "path_a": {
                    "intermediate_length": len(results["path_a"]["intermediate"]),
                    "back_to_english_length": len(results["path_a"]["back_to_english"]),
                },
                "path_b": {
                    "intermediate_length": len(results["path_b"]["intermediate"]),
                    "back_to_english_length": len(results["path_b"]["back_to_english"]),
                },
                "baseline": {
                    "intermediate_length": len(results["baseline"]["intermediate"]),
                    "back_to_english_length": len(results["baseline"]["back_to_english"]),
                },
                "analysis_score": analysis["score"],
            })


if __name__ == "__main__":
    main()
