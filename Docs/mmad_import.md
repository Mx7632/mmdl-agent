# MMAD Import

The project can import the official MMAD metadata into local JSONL files without
copying source images or modifying the MMAD repository.

## Source

Expected local source:

```powershell
E:\Computer\Projects\30_research\mmad
```

The importer reads:

- `dataset/MMAD/mmad.json`
- `dataset/MMAD/domain_knowledge.json`
- image and mask paths referenced by the metadata

`mmad.json` is the preferred source because it contains the full benchmark:
8,366 images and 39,670 multiple-choice questions in the local copy that was
inspected.

## Import A Small Sample

```powershell
python scripts\import_mmad_dataset.py `
  --source-root E:\Computer\Projects\30_research\mmad `
  --metadata-file "mmad.json" `
  --output-root data\mmad_sample `
  --dataset DS-MVTec `
  --category bottle `
  --limit 3
```

Outputs:

- `data/mmad_sample/annotations.jsonl`
- `data/mmad_sample/qa.jsonl`

Imported files under `data/mmad*/` are local artifacts and are ignored by Git.

## Output Shape

Each annotation row keeps image-level context:

- dataset/category/defect type
- resolved image path
- resolved mask path
- similar and random templates
- domain knowledge
- QA items grouped into the project MMAD seven-task shape

Each QA row is flattened for evaluation:

- `task`
- `original_type`
- `question`
- `options`
- `answer`
- `answer_text`
- `image_path`
- `mask_path`

MMAD question types are mapped into the project tasks as:

- `Anomaly Detection` -> `anomaly_discrimination`
- `Defect Classification` -> `defect_classification`
- `Defect Localization` -> `defect_localization`
- `Defect Description` -> `defect_description`
- `Defect Analysis` -> `defect_analysis`
- `Object Classification` -> `object_classification`
- `Object Structure`, `Object Details`, `Object Analysis` -> `object_analysis`
