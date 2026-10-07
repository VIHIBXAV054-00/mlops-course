# Week 4 — Data Versioning — Study Notes

These notes go with the Week 4 lecture and lab. Last week's traceability chain went from a deployed alias back to a model version, a run, its parameters and its git commit. Then it stopped at a file path. This week the chain reaches the data itself.

## Why this matters

In 2020, many research groups trained models to diagnose COVID-19 from chest X-rays and CT scans. A review in 2021 found 2,212 studies, screened 415 and reviewed 62 in full. None of the 62 models was of potential clinical use.

One cause the authors named was **"Frankenstein datasets"**: public datasets built from other public datasets and republished under a new name. Nobody could say what was inside them. Some models were trained and tested on the same or overlapping images without anyone knowing.

The everyday version is more simple. Someone adds last month's rows to `train.csv`. Someone else fixes a value in place. A month later the model scores less, and nobody can say what the data looked like before.

### More cases from the lecture

- **Card payments: fraud labels arrive weeks later.** A payment counts as genuine until the cardholder disputes it. Most labels are known only "after several days (e.g. one month)" (Dal Pozzolo et al., 2018). So the same month of data has different labels, depending on the day you copy it. Take a dated snapshot and record its content hash with the model.
- **A photo app: Everalbum (2021).** The company used its users' photos to build face recognition without their consent. The US FTC settlement (press release, 11 Jan 2021) required it to delete three things. They were the photos of users who closed their accounts, the face embeddings made without consent, and "any facial recognition models or algorithms developed with Ever users' photos or videos". You can only obey such an order, and keep the models it does not name, if you know which models were trained on which data.
- **The EU AI Act, Article 10.** For high-risk AI systems, data governance must cover "the origin of data" (10(2)(b)) and preparation steps such as "cleaning, updating" (10(2)(c)). The data must be, as far as possible, "free of errors and complete" (10(3)). A `.dvc` hash and `dvc.lock` answer the first two; the third is Week 5.
- **Public Health England (2020).** 15,841 positive COVID-19 cases were not passed on to contact tracing in time. Some result files were too large for the system that loaded them (PHE statement, 4 Oct 2020). A file that looks fine can still be incomplete: compare the row count with the source before you version it.

The teacher may use other cases instead:

- **ERA5 and ERA5.1**, ECMWF's record of past global weather. For 2000–2006 it had a cold bias of about 0.5–1 K in the lower stratosphere. The corrected years were published as a separate dataset, ERA5.1 (Simmons et al., ECMWF Tech. Memo 859, 2020). In 2021 ECMWF also found a few hundred corrupted fields, out of 3.1 billion. It fixed them in place, under the same name, and asked users to download the files again (ECMWF, "ERA5 CDS: Data corruption");
- face datasets that were withdrawn but stayed in use (Peng et al., 2021);
- the Reinhart–Rogoff spreadsheet error (Herndon et al., 2013).

### When is data versioning too much?

Our dataset is 31,750 bytes; Git could store it. DVC adds a remote, keys, a second push and a cache. It is worth it when data is large, changes, or is shared. For a small file that never changes, keep it in Git and record its hash. For a public dataset with official versions, record the provider's version.

## Core concepts

### What a hash is

A **hash function** turns any input into a short, fixed-length fingerprint. DVC uses md5, which gives 32 hex characters.

- The same input always gives the same hash.
- Change one character, and the whole hash changes. The first patient row of our dataset, `6,148,72,35,0,33.6,0.627,50,1`, has the md5 `a08191bbcd6221f06a9c23efe7263d38`. With a BMI of 33.7 instead of 33.6, it is `094517dc7d352d3d8b39a247ad17134c`.
- You cannot rebuild the data from its hash.

MD5 is not safe against someone who forges data on purpose, but it is fine for noticing a change.

### Three ways to name a dataset

- A **path** (`data/train.csv`) names a location. The content can change while the name stays the same.
- A **timestamp** (`train_2026_03_04.csv`) names a moment. Two people can save different data on the same day.
- A **content hash** (`md5: 786c54f2…`) is computed from the file content. Different content always gives a different name.

Storing objects under a name computed from their content is called **content-addressed storage**.

### Why Git is the wrong tool for data

Git keeps every version of every file in every clone. For code this is what you want. For data it is a problem:

- a 200 MB file committed ten times is 2 GB in every clone;
- a diff of a binary file tells you nothing;
- you cannot remove the data from history later;
- GitHub blocks files larger than 100 MiB.

So we split the job: **Git keeps the pointer, an object store keeps the data.**

### Data version control tools

Several tools version data. They solve the same problem in different ways:

- **DVC**: Git-based, for data science projects. It names data by its md5.
- **lakeFS**: branches and commits over object storage, for large data lakes.
- **Git LFS**: pointer files in Git, large files on a server. It names data by `oid sha256:…`.
- **Delta Lake**: tables with versions and "time travel" (`VERSION AS OF 12`).
- **Dolt**: a SQL database with Git-style branches.

DVC and Git LFS name data by its content. Delta Lake and S3 bucket versioning give each write a new version number or ID instead. The course uses DVC because it is open source, works next to Git, and stores data in any S3-compatible bucket, such as our Silo. In November 2025 lakeFS took over the DVC project; DVC stays open source under the same licence (DVC blog, 18 Nov 2025).

The practice (a fixed identity for every data version, recorded with the model) is what you take to your next team, whichever tool it uses.

### Installing DVC and `dvc init`

```bash
uv add "dvc[s3]"                  # the [s3] extra adds S3 and S3-compatible stores
dvc init                          # run it inside a Git repository
git commit -m "Initialise DVC"
```

`dvc init` creates `.dvc/config` (settings, such as the remote), `.dvc/.gitignore` (keeps the cache out of Git) and `.dvcignore` (files DVC should not look at), and stages them with `git add`. The cache folder appears later, on the first `dvc add`. The lab is a subfolder of the course repository, so it uses `dvc init --subdir`.

### DVC: pointers in Git, data in Silo

DVC does not have its own history. Git does the versioning.

`dvc add data/measurements.csv` does three things:

1. It computes the file's md5 and stores the file in the local DVC cache.
2. It writes a small **pointer file**, `data/measurements.csv.dvc`, with four fields: `md5`, `size`, `hash` and `path`.
3. It adds the data file to `data/.gitignore`, so Git does not track it.

You commit the pointer file to Git. `dvc push` uploads the data to a **remote**, here the `dvc-storage` bucket in Silo.
The object is stored at `files/md5/<first 2 characters>/<other 30 characters>`.

Because the name is the hash, duplicates cost nothing: pushing the same data twice uploads nothing the second time.

```bash
dvc add data/measurements.csv      # workspace -> cache, writes the pointer
git add data/measurements.csv.dvc data/.gitignore
git commit -m "dataset version 1"
dvc push                           # cache -> remote (Silo)
```

### `dvc push`: upload data

`dvc push` uploads the files your `.dvc` files point to, from the local cache to the remote. It skips files the remote already has, because it compares the hashes. Run it next to `git push`: Git gets the pointer, the remote gets the data.

### `dvc pull`: download data

`dvc pull` downloads the data your `.dvc` files point to, into the cache and then into the workspace. It is `dvc fetch` and `dvc checkout` in one command. Use it after `git clone` or `git pull`: Git brings the pointers, `dvc pull` brings the data.

### `dvc checkout`: restore from the cache

`dvc checkout` makes the workspace match the `.dvc` files, using only the local cache. Use it after `git checkout` has moved a pointer to another version. It never uses the network.

### `checkout` and `pull`

If a version is not in your cache, `dvc checkout` fails. The fix is `dvc pull`, which downloads from the remote first.

### Going back to an earlier version

It takes two commands:

```bash
git checkout HEAD~1 -- data/measurements.csv.dvc   # the pointer
dvc checkout                                       # the data
```

Git chooses the version. DVC delivers the data.

Lab: Exercise 4

### The pipeline: `dvc.yaml`, `dvc repro`, `dvc.lock`

`dvc.yaml` declares **stages**. Each stage names four things:

- `cmd`: the command it runs;
- `deps`: the files it reads, including source code;
- `params`: the parameters it uses, from `params.yaml`;
- `outs`: the files it writes.

`dvc repro` runs only the stages whose inputs changed. It compares **content hashes**, not file times like `make`. Touching a file changes nothing. Changing `train.C` re-runs `train` and `evaluate`, but not `prepare`.

`dvc.lock` records what actually ran: the hash of every dependency and the value of every parameter. Commit it.

Hyperparameters live in `params.yaml`, not in `.env`, because DVC can only hash files. A value in an environment variable would be invisible to `dvc.lock`.

### Running the pipeline: `dvc repro`, `dvc status`, `dvc dag`

```bash
dvc repro     # run every stage that is out of date, in order
dvc status    # show which deps and outs changed since the last run
dvc dag       # draw the graph of stages
```

For each stage, `dvc repro` hashes the `deps`, reads the `params` and compares them with the last run in `dvc.lock`. If nothing changed, it prints "didn't change, skipping". If something changed, it runs `cmd` and records the new hashes. `dvc dag --mermaid` prints the graph as a Mermaid diagram; the versioned dataset is its root.

`dvc repro` decides **what** is out of date. It has no schedule, retries or alerts, so it does not decide **when** the pipeline runs. In Week 7 CI runs it, and in Week 8 a Prefect flow calls `dvc repro` as one task.

### Linking the data version to the MLflow run

In Week 3 the run logged `data_path` and `n_rows`. Both stay the same when someone edits every value in the file.

This week every training run records the data version as **tags**:

- `dvc_md5`: the hash, read from the `.dvc` file (not computed again);
- `dvc_url`: where DVC stored that data, such as `s3://dvc-storage/…`;
- next to Week 3's `git_commit`, so the run names its code **and** its data.

It is a tag because tags exist so that someone can **find** a run (Week 3). Tag every training run when the run is made. Tags are searchable, so you can ask which runs trained on a given version of the data:

```python
mlflow.search_runs(filter_string="tags.dvc_md5 = 'a8fd7b4f0d6d1bc4e378a8f76c5fff0c'")
```

### MLflow's own dataset logging

MLflow has a dataset API: `mlflow.data.from_pandas` and `mlflow.log_input`. It records a name and a context (`training`) and the **source**: where the data is, such as an `s3://` URI. It also records a schema, a profile (for our data: 9 columns, 768 rows) and a **digest**. Runs can be searched by it: `dataset.digest = '9a465ecc'`.

MLflow stores a **description** of the data, not the data. To get the data back you still need DVC.

The two hashes answer different questions:

| | DVC md5 | MLflow digest |
| --- | --- | --- |
| Hashes | the file's exact content | the values of the first 10,000 rows, the row count and the column names |
| Our file (version 3) | `a8fd7b4f0d6d1bc4e378a8f76c5fff0c` | `9a465ecc` |
| Same values, Windows line endings | changes: `d2384a69…` | stays `9a465ecc` |
| Answers | "is this exactly the same file?" | "is this roughly the same table?" |

Editing one BMI value changes both (the digest becomes `3748223f`). For an audit, use the md5; the digest is a quick check that a table changed.

### Beyond one CSV file

The lab versions one CSV. Other data needs other steps; the practice (a fixed version, recorded with the model) stays the same.

- **A folder of files, such as images.** `dvc add data/scans` writes one pointer, `scans.dvc`, whose md5 ends in `.dir`. That `.dir` object lists every file with its own hash. Measured with three images: the first `dvc push` sent 4 files (3 images and the list); after changing one image, it sent 2. For tens of thousands of small files, the DVC docs suggest lakeFS.
- **A database.** DVC versions files, and a live database has nothing fixed to hash. Take a snapshot: `dvc import-db --sql "SELECT …" --conn <name> -o data/patients.csv` writes a CSV (or JSON) and keeps the query, so `dvc update` can repeat it and give a new version. If the tables themselves need history, use a tool built for tables: Delta Lake, Dolt or lakeFS.
- **A file in someone else's bucket.** `dvc import-url` tracks it, and `dvc update` checks it for changes.
- **Data in another DVC repository.** `dvc import` downloads it and records the repository and the version.

## Red flags and good practices

### Byte-exact hashing and line endings

DVC 3 hashes the exact content of a file. A CSV with Windows line endings (CRLF) differs from the same CSV with LF. So it gets a different md5, and `dvc status` says "modified" although nobody changed the data. Fix the line endings of data files in `.gitattributes` (`*.csv text eol=lf`), and write data files with `\n` in your code.

### Automate commands that must run together

A teammate commits the new `.dvc` file and runs `git push`, but forgets `dvc push`. It works on their laptop, from their cache; on yours, `dvc pull` fails, because the remote has no file with that hash. Run `dvc install` once per clone: it adds Git hooks, and the `pre-push` hook runs `dvc push` before every `git push` (the others run `dvc checkout` after `git checkout` and `dvc status` before `git commit`).

### Storage keys in a committed file

`.dvc/config` is committed to Git, so a key written there is shared with everyone who can read the repository and stays in the history. `dvc remote modify myremote secret_access_key …` writes it there. Add `--local`, and the key goes to `.dvc/config.local`, which Git ignores. Or pass the keys as environment variables, as the lab's Makefile does.

### Training on data you have not added

You fix a few rows in `data/measurements.csv` and train at once, before `dvc add`. The run's `dvc_md5` tag comes from the `.dvc` file, so it names the old data: the record looks complete and is wrong, like a `git_commit` from uncommitted code. Before a run you want to keep, `dvc status` must say "Data and pipelines are up to date." If not, run `dvc add` and commit first.

Lab: Exercise 7

## Commands

| Command | What it does |
| --- | --- |
| `dvc init` | starts a DVC project in a Git repository |
| `dvc add <file or folder>` | hashes the data, stores it in the cache, writes the `.dvc` pointer |
| `dvc push` / `dvc pull` | uploads to / downloads from the remote |
| `dvc checkout` | restores the workspace from the cache, as the pointers say |
| `dvc status` | shows data and stages that changed |
| `dvc repro` | runs the stages that are out of date |
| `dvc dag` | draws the stage graph |
| `dvc install` | adds Git hooks, so `git push` also runs `dvc push` |
| `dvc import-db`, `dvc import-url`, `dvc import` | snapshots a database, tracks an external file, or imports from another DVC repository |

## Key terms

- **Content-addressed storage**: objects are stored under a name computed from their content.
- **Content hash (md5)**: a short fingerprint computed from a file's content.
- **Pointer file (`.dvc`)**: the small file in Git that names the data by its hash.
- **DVC cache**: the local copy of tracked data, in `.dvc/cache`. Never committed.
- **DVC remote**: shared storage for the data; here a Silo bucket.
- **Stage**: one step of a DVC pipeline, with `cmd`, `deps`, `params` and `outs`.
- **`dvc.lock`**: the record of what a pipeline run actually used.
- **Dataset digest (MLflow)**: MLflow's short hash of a table's values. Not a byte hash.
- **Hash function**: turns any input into a short, fixed-length fingerprint; the same input always gives the same hash.
- **Data version control**: giving every version of a dataset a fixed identity, and recording which version was used where.
- **`.dir` object**: the list DVC stores for a tracked folder, with each file's own hash.
- **Git hook**: a script Git runs before or after a command; `dvc install` adds hooks for `push`, `checkout` and `commit`.
- **Local config (`.dvc/config.local`)**: DVC settings that Git ignores; the place for keys.
- **Snapshot**: a copy of data fixed at one moment, such as the result of a database query saved to a file.
- **Consent**: a person's permission to use their data. It can be withdrawn.
- **Line ending**: the characters that end a line in a text file: LF on macOS and Linux, CRLF on Windows.
- **Stratosphere**: the layer of the atmosphere above about 10–15 km.
- **Settlement**: an agreement that ends a legal case.

## How this connects to the lab

The lab uses the Week 3 Compose stack, plus a second Silo bucket, `dvc-storage`. You:

1. set up DVC and point it at Silo, with no keys in Git;
2. receive the first batch, build dataset version 1 (461 rows), add it, read the pointer, push it, and find it in Silo;
3. delete the cache and see `dvc checkout` fail and `dvc pull` succeed;
4. receive two more batches (versions 2 and 3, 568 and 768 rows) and go back to version 1;
5. declare `train` and `evaluate` in `dvc.yaml`, and see which stages re-run after a change;
6. tag the MLflow run with the data's md5, and compare it with MLflow's digest;
7. (optional) edit one value without `dvc add`, see the run name the wrong data, and add a check that stops it.


## Recommended reading

- **Designing Machine Learning Systems (Huyen), Ch. 3–4.** *Focus on:* why "which data" is a hard question in practice.
- **DVC documentation: Get Started, and the S3 remote guide** (https://doc.dvc.org/start). *Focus on:* the `.dvc` file, `add`/`push`/`pull`/`checkout`, and the `endpointurl` setting that points an "S3" remote at Silo.
- **Gebru et al., "Datasheets for Datasets"**, *Communications of the ACM* 64(12), 2021. *Focus on:* what to write down about a dataset besides its version.
- **Roberts et al.**, *Nature Machine Intelligence* 3, 199–217 (2021). *Focus on:* the section on datasets and "Frankenstein datasets".
- Optional: **MLflow documentation: Datasets.** *Focus on:* what `log_input` records.

(More reading: `docs/resources.md`.)

## Check yourself

1. A colleague edits three values in `data/measurements.csv`. `git status` shows nothing to commit. Why? What does `dvc status` say?
2. You run `git checkout HEAD~1 -- data/measurements.csv.dvc` on a laptop that never pulled that version. What does `dvc checkout` do, and what is the fix?
3. `dvc repro` says "Stage 'train' didn't change, skipping", but you edited `model.py`. Give two possible reasons.
4. An auditor asks which exact data trained the model in production. Do you give the MLflow digest or the DVC md5? Why?
5. Your project's dataset is 20 KB and never changes. Would you use DVC? What would you record instead?
6. A regulator orders you to delete every model trained on one customer's data. Which record from this week lets you find those models?
7. A teammate ran `git push` but forgot `dvc push`. What happens when you run `dvc pull`, and which command would have prevented it?
8. The same CSV is saved with Windows line endings. Which changes: the DVC md5, the MLflow digest, or both?
9. You need to give DVC the key for your team's bucket. Where do you put it, so that it never reaches Git?
10. Your training data lives in a PostgreSQL database. How do you give it a version that DVC can track?
11. Why does the course use DVC and not lakeFS? When would lakeFS be the better choice?
