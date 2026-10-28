"""Phone layout: everything readable at 390 px wide with no sideways scrolling, and nothing cut off."""
import streamlit as st

CSS = """<style>
@media (max-width:760px){
  /* home: the live example card fits the screen; a shorter 3D carton so the buttons come sooner */
  .sc-side{flex-basis:100%;max-width:100%;min-width:0}
  .sc-side .sc-pv{position:relative;width:100%;box-sizing:border-box;right:auto;top:auto}
  .sc-mascot{height:240px!important}
}
@media (max-width:640px){
  /* home on a phone: the headline, the carton and the buttons; the longer copy lives in the Guide */
  .sc-hero .sc-kicker,.sc-hero p,.sc-hero .sc-chips,.sc-side .sc-pv{display:none!important}
  .sc-hero{padding:22px 18px 10px!important}
  .sc-mascot{height:210px!important}
  /* other pages: the title alone, without the grey description under it */
  [data-testid='stElementContainer']:has([data-testid='stHeading'] h1)+[data-testid='stElementContainer']
    [data-testid='stCaptionContainer']{display:none}
  [data-testid='stMainBlockContainer']{padding-left:1rem;padding-right:1rem}
  [data-testid='stHeading'] h1{font-size:1.7rem}
  /* example phrases wrap instead of being cut off */
  [data-testid='stButtonGroup'] button{max-width:100%;height:auto;text-align:left}
  [data-testid='stButtonGroup'] button *{white-space:normal!important;text-overflow:clip!important}
  /* the three status cards stay in one row */
  .st-key-tile-row{flex-wrap:nowrap!important}
  .st-key-tile-row>div{min-width:0!important;flex:1 1 0!important}
  /* the booking's four numbers as a 2 x 2 grid */
  [class*='st-key-bk-metrics']{display:grid!important;grid-template-columns:1fr 1fr;gap:.5rem!important}
  [class*='st-key-bk-metrics']>div{width:auto!important;min-width:0!important}
  [class*='st-key-bk-metrics'] [data-testid='stMetricValue']{font-size:1.45rem}
  /* a shorter chat window, so the message box is on screen */
  .st-key-chat-history{height:46vh!important;max-height:46vh!important;min-height:300px}
}
</style>"""


def style():
    st.html(CSS)
