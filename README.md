# GeoJSON ↔ CSV Bulk Editor

A Streamlit application for bulk-editing GeoJSON properties through CSV/XLSX workflows, with an emphasis on uMap data preparation.

## Workflows

The application includes:

- combining multiple GeoJSON files;
- GeoJSON → CSV conversion;
- CSV → GeoJSON conversion;
- merging edited attributes back into GeoJSON;
- joining attributes from CSV, XLSX, or GeoJSON data;
- CSV encoding fallbacks for UTF-8, Latin-1, and CP1252.

The tabular representation keeps feature ID and geometry JSON alongside the editable properties.

## Requirements

Python 3 and the packages listed in `requirements.txt`.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Important

Do not edit the `geometry_json` column when working in Excel. Edit the attribute/property fields and preserve the geometry data.

## License

See [LICENSE](LICENSE).

## AI-Assisted Development

This project was developed and/or maintained with AI assistance. AI was used to support parts of the design, implementation, documentation, and/or maintenance workflow. The human maintainer remains responsible for reviewing, validating, and approving the project's code and outputs.
