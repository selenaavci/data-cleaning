# Data Cleaning Agent

## Overview
Data Cleaning Agent is a lightweight AI Hub module designed to automatically identify and resolve common data preparation issues in uploaded CSV and Excel datasets. Its goal is to reduce manual preprocessing effort by applying safe, transparent, and configurable cleaning operations before downstream analytics or machine learning steps.

This agent is built for internal enterprise use cases where business users or analysts need a practical way to standardize raw data without writing code. Instead of only reporting issues, the agent can also apply corrective actions and generate a cleaned output file together with a summary of all transformations performed.

---

## Purpose
Raw datasets often contain missing values, inconsistent text formats, duplicated rows, invalid characters, mixed date formats, and incorrect data types. These problems slow down analysis, reduce model quality, and create trust issues in reporting.

The purpose of the Data Cleaning Agent is to provide an easy-to-use interface where users can upload their dataset, review detected cleaning opportunities, optionally apply automated fixes, and download a cleaned version of the data with a transparent transformation report.

---

## Core Capabilities

### 1. Missing Value Handling
The agent detects missing values at both column and row level and applies configurable handling strategies such as:
- Fill numeric columns with mean, median, or zero
- Fill categorical columns with mode or placeholder values
- Drop rows or columns exceeding a missingness threshold

### 2. Duplicate Detection and Removal
The agent identifies:
- Full row duplicates
- Exact repeated records
- Optionally duplicate IDs or repeated business keys

It can remove duplicates and export a cleaned dataset.

### 3. Data Type Standardization
The agent checks whether columns are consistent with their expected structure and can:
- Convert numeric-looking text into numeric columns
- Parse date-like strings into datetime format
- Normalize boolean-like values such as Yes/No, True/False, 1/0

### 4. Text Standardization
The agent supports cleaning of string columns through:
- Trimming leading and trailing whitespace
- Lowercasing or uppercasing
- Removing extra spaces
- Standardizing special characters
- Optional punctuation cleanup

### 5. Invalid / Suspicious Value Detection
The system can flag values such as:
- Negative numbers where they are not expected
- Empty strings disguised as real values
- Placeholder values such as `N/A`, `-`, `unknown`, `null`
- Columns with mixed formats

### 6. Outlier-Aware Cleaning Support
For selected numeric columns, the agent can optionally apply safe preprocessing actions such as:
- IQR-based outlier flagging
- Winsorization
- Capping extreme values

### 7. Cleaning Summary and Export
Every cleaning action is logged into a structured summary so users can clearly see:
- What was detected
- What was changed
- Which columns were affected
- How many rows were modified or removed

---

## Target Users
This agent is designed for:
- Business analysts
- Data analysts
- BI teams
- ML engineers
- Operations teams
- Internal users who work with Excel or CSV files

---

## Example Use Cases

### Example 1: Customer Data Preparation
A user uploads a customer dataset where phone numbers are stored inconsistently, some ages are missing, and duplicate customer rows exist. The agent standardizes formats, fills safe missing values, removes duplicates, and produces a cleaner version for reporting.

### Example 2: Preprocessing Before Modeling
A team wants to run segmentation or anomaly detection on a raw operational dataset. Before downstream agents are used, the Data Cleaning Agent prepares the dataset and removes technical issues that could distort results.

### Example 3: Excel-Based Operational Data Cleanup
An operations team exports a monthly report from a legacy system. The file contains blank cells, inconsistent dates, and repeated records. The agent quickly prepares a reliable version for further analysis.

---

## End-to-End Workflow

1. The user uploads a CSV or Excel dataset.
2. The system reads the file and validates whether it is usable.
3. Column-level and row-level cleaning opportunities are detected.
4. The user reviews suggested cleaning actions.
5. Selected cleaning operations are applied.
6. The cleaned dataset is generated.
7. The user downloads:
   - Cleaned data file
   - Cleaning summary report

---

## Supported Cleaning Operations

- Missing value imputation
- Row/column removal based on thresholds
- Duplicate row removal
- Text normalization
- Invalid placeholder cleanup
- Numeric parsing
- Date parsing
- Boolean normalization
- Outlier capping or winsorization
- Empty string replacement

---

## User Interface
The agent is intended to run with a simple Streamlit-based interface inside the internal AI Hub environment.

### Suggested UI Sections
- File Upload
- Dataset Preview
- Cleaning Options Panel
- Detected Issues Summary
- Applied Transformations Summary
- Download Buttons

### Download Outputs
- `cleaned_dataset.xlsx` or `cleaned_dataset.csv`
- `cleaning_summary.xlsx` or `cleaning_summary.csv`

---

## Technical Approach

### Input Support
- CSV
- XLSX

### Core Processing Components
- File reader and validator
- Type inference engine
- Missing value analyzer
- Duplicate detector
- Text normalization module
- Safe transformation pipeline
- Export manager

### Possible Python Libraries
- pandas
- numpy
- openpyxl
- scikit-learn (optional for preprocessing utilities)
- streamlit

---

## Design Principles

### 1. Transparency
The agent should never silently change data without reporting it. Every transformation must be traceable.

### 2. Safety
Default behavior should prefer low-risk cleaning actions. Aggressive operations such as dropping rows should be optional.

### 3. Configurability
Users should be able to choose or disable specific cleaning steps depending on the dataset.

### 4. Reusability
The cleaned output should be directly usable by other AI Hub agents such as anomaly detection, segmentation, or reporting modules.

---

## Example Output Artifacts

### Cleaned Dataset
A cleaned and standardized version of the original dataset.

### Cleaning Summary
A transformation log including fields such as:
- Column Name
- Issue Type
- Cleaning Action
- Number of Affected Rows
- Status

### Optional Metrics
- Total rows before cleaning
- Total rows after cleaning
- Number of duplicates removed
- Missing value reduction rate
- Number of columns standardized

---

## Benefits

- Reduces manual preprocessing time
- Improves downstream model quality
- Makes raw enterprise data easier to trust
- Standardizes datasets before analysis
- Helps non-technical users prepare data without coding

---

## Limitations
This agent is designed for common and safe preprocessing tasks. It is not intended to replace deep domain-specific data engineering pipelines or fully automated master data management systems.

Very sensitive business rules, semantic corrections, or domain logic validations should be handled by dedicated agents or custom rule modules.

---

## Future Enhancements
Potential future improvements may include:
- Fuzzy duplicate detection
- Business rule validation
- Column recommendation engine
- Auto-generated cleaning quality score
- Integration with Data Quality Agent for issue classification before cleaning
- Optional human-in-the-loop approval workflow

