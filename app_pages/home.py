import streamlit as st

st.title("Shipment pre-flight checker")
st.write("Book a shipment from the UK to Germany, France or the Netherlands and catch mistakes "
         "**before** it leaves — so your stock isn't held at customs or reported missing at the warehouse.")

with st.container(horizontal=True):
    with st.container(border=True):
        st.markdown("### :material/chat: Book by chat")
        st.write("Describe your shipment in plain English. We only ask for what's missing.")
        st.page_link("app_pages/chat_booking.py", label="Start a chat booking", icon=":material/arrow_forward:")
    with st.container(border=True):
        st.markdown("### :material/upload_file: Upload a file")
        st.write("Upload your Bookings and Items sheets and check every booking at once.")
        st.page_link("app_pages/upload_file.py", label="Upload bookings", icon=":material/arrow_forward:")

st.markdown("#### What we check")
st.markdown(
    "- **Customs paperwork** — HS codes (the international code customs uses to classify a product), "
    "declared value vs items, country of origin, and dangerous goods (lithium batteries, aerosols, "
    "flammable liquids).\n"
    "- **Counts** — units per carton × cartons = quantity, and booking cartons = item cartons, so the "
    "warehouse doesn't report anything missing.\n"
    "- **Weights** — weight per pallet (a pallet is the platform the cartons are stacked on) within the "
    "carrier's limit, and gross weight at least the weight of the goods.\n"
    "- **Logistics** — a delivery slot at warehouses, and a ready date that isn't in the past.")
st.caption(":red-badge[Red] must be fixed before shipping · :orange-badge[Amber] warning, should be fixed")
