"""
Streamlit app: GeoJSON <-> CSV bulk properties editor workflow
- UTF-8 → Latin-1/CP1252 fallback
- Combine multiple GeoJSON files
- Step C: Stand-alone Join Attributes
"""

import streamlit as st
import pandas as pd
import json
import io
from typing import List, Dict, Any

st.set_page_config(page_title="GeoJSON ↔ CSV Bulk Editor", layout="wide")
st.title("GeoJSON ↔ CSV Bulk Editor — bulk-edit properties for uMap workflow")

DEFAULT_EXAMPLE_PATH = "/mnt/data/baee1fac-2f34-4d13-a83e-39ceda97409b.png"
st.info("🚨 **PENTING**: Jangan edit kolom `geometry_json` di Excel. Hanya edit kolom properties (nama, jenis, dsb).")

# --- Helper functions ---
def read_csv_with_fallback(file_buffer):
    try:
        file_buffer.seek(0)
        df = pd.read_csv(file_buffer, encoding='utf-8', dtype=str, keep_default_na=False)
        st.success("✅ CSV dibaca dengan encoding: UTF-8")
        return df
    except UnicodeDecodeError:
        st.warning("❌ UTF-8 gagal, mencoba Latin-1...")
    try:
        file_buffer.seek(0)
        df = pd.read_csv(file_buffer, encoding='latin-1', dtype=str, keep_default_na=False)
        st.success("✅ CSV dibaca dengan encoding: Latin-1")
        return df
    except UnicodeDecodeError:
        st.warning("❌ Latin-1 gagal, mencoba CP1252...")
    try:
        file_buffer.seek(0)
        df = pd.read_csv(file_buffer, encoding='cp1252', dtype=str, keep_default_na=False)
        st.success("✅ CSV dibaca dengan encoding: CP1252")
        return df
    except Exception as e:
        st.error(f"❌ Semua encoding gagal: {e}")
        raise

def geojson_to_dataframe(geojson: Dict[str, Any]) -> pd.DataFrame:
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
        for k, v in props.items():
            if k in row:
                row[f"prop_{k}"] = v
            else:
                row[k] = v
        rows.append(row)
    df = pd.DataFrame(rows)
    cols = ["_feature_id", "geometry_json"] + [c for c in df.columns if c not in ("_feature_id", "geometry_json")]
    return df[cols]

def dataframe_to_geojson(df: pd.DataFrame) -> Dict[str, Any]:
    features = []
    for _, row in df.iterrows():
        geom_json = row.get("geometry_json")
        try:
            geom = json.loads(geom_json) if pd.notna(geom_json) and geom_json is not None else None
        except Exception as e:
            st.error(f"Invalid geometry JSON for feature id={row.get('_feature_id')}: {str(e)}")
            geom = None
        props = {}
        for col in df.columns:
            if col in ("geometry_json", "_feature_id"):
                continue
            val = row[col]
            if pd.isna(val) or val == '':
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

def combine_geojson_files(geojson_files: List[Dict[str, Any]]) -> Dict[str, Any]:
    all_features = []
    feature_ids = set()
    for i, geojson_obj in enumerate(geojson_files):
        features = geojson_obj.get("features", [])
        st.info(f"📁 File {i+1}: {len(features)} features")
        for feature in features:
            original_id = feature.get("id")
            if original_id and original_id in feature_ids:
                counter = 1
                new_id = f"{original_id}_{counter}"
                while new_id in feature_ids:
                    counter += 1
                    new_id = f"{original_id}_{counter}"
                feature["id"] = new_id
                st.warning(f"⚠️ Duplicate ID '{original_id}' renamed to '{new_id}'")
            if feature.get("id"):
                feature_ids.add(feature["id"])
            all_features.append(feature)
    return {"type": "FeatureCollection", "features": all_features}

def join_attributes(base_df: pd.DataFrame, join_df: pd.DataFrame, key: str, suffix="_joined") -> pd.DataFrame:
    join_cols = [c for c in join_df.columns if c not in [key, "geometry_json"]]
    df_joined = base_df.merge(
        join_df[[key] + join_cols],
        on=key,
        how='left',
        suffixes=("", suffix)
    )
    return df_joined

# --- Step 0: Combine multiple GeoJSON ---
st.header("🔄 Step 0 — Combine Multiple GeoJSON Files")
multi_geojson_files = st.file_uploader(
    "Upload multiple GeoJSON files (.geojson or .json)", 
    type=["geojson", "json"], 
    key="multi_geo",
    accept_multiple_files=True
)
if multi_geojson_files and len(multi_geojson_files) > 1:
    geojson_objects = []
    valid_files = True
    for i, uploaded_file in enumerate(multi_geojson_files):
        try:
            geojson_obj = json.load(uploaded_file)
            if geojson_obj.get("type") == "FeatureCollection":
                geojson_objects.append(geojson_obj)
                st.success(f"✅ File {i+1}: {uploaded_file.name} - Valid FeatureCollection")
            else:
                st.error(f"❌ File {i+1}: {uploaded_file.name} - Not a FeatureCollection")
                valid_files = False
        except Exception as e:
            st.error(f"❌ File {i+1}: {uploaded_file.name} - Error: {e}")
            valid_files = False
    if valid_files and geojson_objects:
        try:
            combined_geojson = combine_geojson_files(geojson_objects)
            total_features = len(combined_geojson["features"])
            st.success(f"✅ Combined {len(geojson_objects)} files into {total_features} features")
            st.subheader("👀 Preview Combined GeoJSON (first 3 features)")
            for i, feature in enumerate(combined_geojson["features"][:3]):
                st.write(f"**Feature {i+1}:**")
                st.json(feature)
            combined_geo_str = json.dumps(combined_geojson, indent=2, ensure_ascii=False)
            st.download_button(
                "💾 Download Combined GeoJSON", 
                data=combined_geo_str.encode("utf-8"), 
                file_name="combined.geojson", 
                mime="application/json",
                key="download_combined"
            )
            if st.button("🔄 Use Combined GeoJSON for Step A"):
                st.session_state.combined_geojson = combined_geojson
                st.success("✅ Combined GeoJSON ready for Step A!")
        except Exception as e:
            st.error(f"❌ Error combining GeoJSON files: {e}")

# --- Step A: Upload GeoJSON → Convert CSV ---
st.header("📥 Step A — Convert GeoJSON → CSV")
col1, col2 = st.columns([1,1])
with col1:
    uploaded_geojson = st.file_uploader("Upload GeoJSON (.geojson or .json)", type=["geojson","json"], key="upload_geo")
    paste_geo_text = st.text_area("Atau paste GeoJSON di sini (optional)", height=120)
with col2:
    st.write("📋 Instructions: Edit only properties, not geometry_json or _feature_id")

geojson_obj = None
if 'combined_geojson' in st.session_state:
    geojson_obj = st.session_state.combined_geojson
elif uploaded_geojson:
    try:
        geojson_obj = json.load(uploaded_geojson)
        st.success("✅ GeoJSON berhasil di-load")
    except Exception as e:
        st.error(f"❌ Gagal parse GeoJSON: {e}")
elif paste_geo_text.strip() != "":
    try:
        geojson_obj = json.loads(paste_geo_text)
        st.success("✅ GeoJSON dari teks berhasil di-load")
    except Exception as e:
        st.error(f"❌ Gagal parse GeoJSON dari teks: {e}")

if geojson_obj:
    df_out = geojson_to_dataframe(geojson_obj)
    st.subheader("👀 Preview CSV hasil convert (10 baris pertama)")
    st.dataframe(df_out.head(10))
    csv_buffer = io.StringIO()
    df_out.to_csv(csv_buffer, index=False, encoding='utf-8')
    st.download_button(
        "💾 Download CSV untuk diedit di Excel", 
        data=csv_buffer.getvalue().encode("utf-8"), 
        file_name="export_properties.csv", 
        mime="text/csv"
    )

# --- Step B: Upload edited CSV → Merge → GeoJSON ---
st.markdown("---")
st.header("📤 Step B — Upload CSV hasil edit → Merge → Download GeoJSON")
edited_csv = st.file_uploader("Upload CSV yang sudah diedit", type=["csv"], key="upload_csv")
if edited_csv:
    try:
        df_edited = read_csv_with_fallback(edited_csv)
        st.subheader("👀 Preview CSV (setelah edit)")
        st.dataframe(df_edited.head(10))
        if "geometry_json" not in df_edited.columns:
            st.error("❌ CSV tidak mengandung kolom 'geometry_json'")
        else:
            df_edited = df_edited.replace(['','NaN','NaT','None'], None).where(pd.notna(df_edited), None)
            geo_out = dataframe_to_geojson(df_edited)
            st.subheader("🔍 Preview GeoJSON (feature pertama)")
            if geo_out.get("features"):
                st.json(geo_out["features"][0])
            geo_str = json.dumps(geo_out, indent=2, ensure_ascii=False)
            st.download_button(
                "💾 Download merged GeoJSON", 
                data=geo_str.encode("utf-8"), 
                file_name="merged.geojson", 
                mime="application/json"
            )
            st.success("✅ GeoJSON berhasil dibuat!")
    except Exception as e:
        st.error(f"❌ Gagal memproses CSV: {e}")

# --- Step C: Stand-alone Join Attributes ---
st.markdown("---")
st.header("🧩 Step C — Stand-alone Join Attributes")
st.info("""
Upload **two files** (main + additional) and join attributes by a shared key column.
- Supported formats: CSV, XLSX, GeoJSON/JSON
- Geometry is preserved if main file is GeoJSON
""")

col1, col2 = st.columns(2)
with col1:
    main_file = st.file_uploader("Upload MAIN file (CSV, XLSX, GeoJSON)", type=["csv","xlsx","geojson","json"], key="main_file")
with col2:
    add_file = st.file_uploader("Upload ADDITIONAL attribute file (CSV, XLSX, GeoJSON)", type=["csv","xlsx","geojson","json"], key="add_file")

join_key_c = st.text_input("Join key column (must exist in both files)", value="_feature_id", key="join_key_c")

if st.button("🔗 Join Attributes (Step C)"):
    if main_file is None or add_file is None:
        st.error("❌ Both files must be uploaded")
    else:
        try:
            # --- Load MAIN file ---
            if main_file.name.lower().endswith(".csv"):
                main_df = read_csv_with_fallback(main_file)
            elif main_file.name.lower().endswith(".xlsx"):
                main_file.seek(0)
                main_df = pd.read_excel(main_file, dtype=str)
            else:
                main_geo = json.load(main_file)
                main_df = geojson_to_dataframe(main_geo)
            
            # --- Load ADDITIONAL file ---
            if add_file.name.lower().endswith(".csv"):
                add_df = read_csv_with_fallback(add_file)
            elif add_file.name.lower().endswith(".xlsx"):
                add_file.seek(0)
                add_df = pd.read_excel(add_file, dtype=str)
            else:
                add_geo = json.load(add_file)
                add_df = geojson_to_dataframe(add_geo)

            # --- Validate key ---
            if join_key_c not in main_df.columns:
                st.error(f"❌ Key '{join_key_c}' not found in MAIN file")
            elif join_key_c not in add_df.columns:
                st.error(f"❌ Key '{join_key_c}' not found in ADDITIONAL file")
            else:
                # --- Perform join ---
                df_joined_c = join_attributes(main_df, add_df, join_key_c)
                st.success("✅ Attributes successfully joined!")
                st.subheader("👀 Preview (first 10 rows)")
                st.dataframe(df_joined_c.head(10))

                # --- Download CSV ---
                csv_buffer_c = io.StringIO()
                df_joined_c.to_csv(csv_buffer_c, index=False, encoding='utf-8')
                st.download_button(
                    "💾 Download CSV after join",
                    data=csv_buffer_c.getvalue().encode("utf-8"),
                    file_name="joined_attributes_stepC.csv",
                    mime="text/csv"
                )

                # --- Optional: Download GeoJSON if main was GeoJSON ---
                if main_file.name.lower().endswith(("geojson","json")):
                    geojson_out_c = dataframe_to_geojson(df_joined_c)
                    geo_str_c = json.dumps(geojson_out_c, indent=2, ensure_ascii=False)
                    st.download_button(
                        "💾 Download GeoJSON after join",
                        data=geo_str_c.encode("utf-8"),
                        file_name="joined_attributes_stepC.geojson",
                        mime="application/json"
                    )

        except Exception as e:
            st.error(f"❌ Failed to join attributes: {e}")
