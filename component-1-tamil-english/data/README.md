# Dataset Management

## Purpose

This directory is intended to contain data resources for the Tamil-English code-mixed hate-speech detection and classification component.

## Data Collection

Datasets will be collected or obtained from sources that permit the intended research use. Original text should be preserved separately from any normalized or preprocessed version.

## Annotation Categories

The planned hate-speech target categories are:

* Racial/Ethnic
* Religious
* Political
* Gender-Based
* Sexual Orientation

Comments that cannot be confidently classified should be marked for review rather than assigned an unsupported label.

## Data Quality

Before model training, datasets must be checked for:

* Missing comments and labels
* Duplicate records
* Language and script composition
* Label consistency
* Train, development, and test split integrity

## Data Handling

Dataset files must be handled according to their licences, applicable privacy requirements, and the research team's data-management decisions.

Large datasets and data that cannot be redistributed should not be committed to the repository. Where necessary, commit dataset preparation scripts, schemas, and instructions for obtaining the data instead.
