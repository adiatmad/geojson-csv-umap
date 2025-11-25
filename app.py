"""
Streamlit app: GeoJSON <-> CSV bulk properties editor workflow
Features:
- Upload GeoJSON -> convert to CSV (properties flattened + geometry as JSON string)
- Download CSV, edit in Excel (DO NOT edit `geometry_json` column)
- Upload edited CSV -> merge properties back with original geometry -> produce valid GeoJSON
- Preview small sample of data and basic validation

Notes for user:
- You must NOT modify the `geometry_json` column in Excel. If you need to edit geometry, use a proper GIS tool (QGIS/uMap editor).
- This app assumes FeatureCollection input GeoJSON.

Developer note: default_example_path is included (from conversation history) as a local placeholder.
"""

import streamlit as st
import pandas as pd
import json
import io
from typing import List, Dict, Any

st.set_page_config(page_title="GeoJSON ↔ CSV Bulk Editor", layout="wide")
st.title("GeoJSON ↔ CSV Bulk Editor — bulk-edit properties for uMap workflow")

# Developer-provided local path from conversation history (placeholder)
DEFAULT_EXAMPLE_PATH = "/mnt/data/baee1fac-2f34-4d13-a83e-39ceda97409b.png"

st.info("Jangan edit kolom `geometry_json` di Excel. Hanya edit kolom properties (nama, jenis, dsb).")

# --- Helpers ---

def geojson_to_dataframe(geojson: Dict[str, Any]) -> pd.DataFrame:
    """Convert GeoJSON FeatureCollection to pandas DataFrame.
    Each row = 1 feature.
    properties are flattened (kept as columns). geometry is stored as JSON string in 'geometry_json'.
    Also include an 'id' column if available (feature['id']) or create one.
    """
    features = geojson.get("features", [])
    rows = []
    for i, feat in enumerate(features):
        props = feat.get("properties", {}) or {}
        geom = feat.get("geometry", None)
        fid = feat.get("id", f"feature_{i}")
        row = {
            "_feature_id": fid,
            "geometry_json": json.dumps(geom) if geom is not None else None,
        }
        # merge props
        for k, v in props.items():
            # avoid collisions with internal columns
            if k in row:
                row[f"prop_{k}"] = v
            else:
                row[k] = v
        rows.append(row)
    df = pd.DataFrame(rows)
    # ensure deterministic column order
    cols = ["_feature_id", "geometry_json"] + [c for c in df.columns if c not in ("_feature_id", "geometry_json")]
    return df[cols]


def dataframe_to_geojson(df: pd.DataFrame) -> Dict[str, Any]:
    """Convert DataFrame back to GeoJSON FeatureCollection.
    Expects 'geometry_json' column containing a JSON geometry for each row.
    All other columns are treated as properties (except internal ones starting with underscore).
    """
    features = []
    for _, row in df.iterrows():
        geom_json = row.get("geometry_json")
        try:
            geom = json.loads(geom_json) if pd.notna(geom_json) and geom_json is not None else None
        except Exception:
            st.error(f"Invalid geometry JSON for feature id={row.get('_feature_id')}")
            geom = None

        props = {}
        for col in df.columns:
            if col in ("geometry_json", "_feature_id"):
                continue
            # convert NaN to None
            val = row[col]
            if pd.isna(val):
                continue
            props[col] = val

        feature = {
            "type": "Feature",
            "properties": props,
            "geometry": geom,
            "id": row.get("_feature_id")
        }
        features.append(feature)

    return {"type": "FeatureCollection", "features": features}


# --- UI: Step 1: Upload GeoJSON and convert to CSV ---
st.header("Step A — Convert GeoJSON → CSV (for bulk editing)")
col1, col2 = st.columns([1, 1])
with col1:
    uploaded_geojson = st.file_uploader("Upload GeoJSON (.geojson or .json)", type=["geojson", "json"], key="upload_geo")
    st.caption("If you don't have a GeoJSON, you can paste the text below or use an example path from the conversation history.")
    example_path = st.text_input("(Optional) Local example path (from conversation history)", value=DEFAULT_EXAMPLE_PATH)
    paste_geo_text = st.text_area("Or paste GeoJSON here (optional)", height=120)
with col2:
    st.write("Instructions:")
    st.markdown("""
- Upload your original GeoJSON FeatureCollection.
- This tool will create a CSV where each row is one feature.
- The `geometry_json` column contains the geometry as a JSON string — **do not edit this column in Excel**.
- Edit only property columns in Excel, then upload the CSV back in Step B to merge.
""")

geojson_obj = None
if uploaded_geojson is not None:
    try:
        geojson_obj = json.load(uploaded_geojson)
    except Exception as e:
        st.error(f"Gagal parse GeoJSON: {e}")
elif paste_geo_text.strip() != "":
    try:
        geojson_obj = json.loads(paste_geo_text)
    except Exception as e:
        st.error(f"Gagal parse GeoJSON dari teks: {e}")
else:
    # show example hint using the local path if present (no auto-load)
    st.caption(f"Contoh lokal path (tidak otomatis dimuat): {example_path}")

if geojson_obj is not None:
    try:
        df_out = geojson_to_dataframe(geojson_obj)
        st.subheader("Preview CSV hasil convert (first 10 rows)")
        st.dataframe(df_out.head(10))

        # CSV download
        csv_buffer = io.StringIO()
        df_out.to_csv(csv_buffer, index=False)
        csv_bytes = csv_buffer.getvalue().encode("utf-8")
        st.download_button("Download CSV untuk diedit di Excel", data=csv_bytes, file_name="export_properties.csv", mime="text/csv")
    except Exception as e:
        st.error(f"Gagal convert GeoJSON → CSV: {e}")

# --- UI: Step 2: Upload edited CSV and merge back to GeoJSON ---
st.markdown("---")
st.header("Step B — Upload CSV hasil edit → Merge → Download GeoJSON")
edited_csv = st.file_uploader("Upload CSV yang sudah kamu edit (dari Step A)", type=["csv"], key="upload_csv")

if edited_csv is not None:
    try:
        df_edited = pd.read_csv(edited_csv, dtype=str)
        st.subheader("Preview CSV (after edit)")
        st.dataframe(df_edited.head(10))

        # Basic validation
        if "geometry_json" not in df_edited.columns:
            st.error("CSV tidak mengandung kolom 'geometry_json'. Pastikan file berasal dari Step A dan jangan hapus kolom ini.")
        else:
            # Merge back to GeoJSON
            # Clean NaN strings
            df_edited = df_edited.where(pd.notna(df_edited), None)
            geo_out = dataframe_to_geojson(df_edited)

            st.subheader("Preview GeoJSON (first feature)")
            if len(geo_out.get("features", [])) > 0:
                st.json(geo_out.get("features")[0])

            geo_str = json.dumps(geo_out, indent=2)
            st.download_button("Download merged GeoJSON", data=geo_str.encode("utf-8"), file_name="merged.geojson", mime="application/json")
            st.success("GeoJSON berhasil dibuat. Silakan download dan upload ke uMap.")
    except Exception as e:
        st.error(f"Gagal memproses CSV: {e}")

# --- Optional: quick validator / small fixes ---
st.markdown("---")
st.header("Validator & Tips")
st.write("Tips singkat untuk menghindari kesalahan saat mengedit di Excel:")
st.markdown("""
- Jangan hapus atau ubah kolom `geometry_json` atau `_feature_id`.
- Jika Excel mengubah format teks (mis. mengubah 00123 menjadi 123), pertimbangkan untuk menyimpan CSV sebagai UTF-8 dan buka sebagai teks di Excel (atau gunakan LibreOffice).
- Jika ada kolom timestamp, pastikan format ISO (`YYYY-MM-DDTHH:MM:SSZ`).
- Jika kamu butuh edit geometry, gunakan QGIS atau editor online, jangan Excel.
""")

st.caption("App ini dibuat otomatis — jika butuh fitur tambahan (WKT support, preview map, auto-repair coordinates), minta saja dan aku tambahkan.")
