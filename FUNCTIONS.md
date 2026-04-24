# MBA 706 Toolkit — Function Quick Reference

All functions are in `mba706_toolkit.py`. Ask Cursor to use any of these by name.

## Data Loading

| Function | What It Does | Key Parameters |
|---|---|---|
| `load_data()` | Load a CSV file | `filepath`, `dataset_name` |
| `load_excel_data()` | Load an Excel file | `filepath`, `sheet_name`, `dataset_name` |

## Data Exploration

| Function | What It Does | Key Parameters |
|---|---|---|
| `get_column_info()` | Column names, types, missing counts | `dataset_name` |
| `get_summary_statistics()` | Descriptive stats for all columns | `dataset_name`, `columns` |
| `calculate_correlation()` | Correlation between two columns | `dataset_name`, `col1`, `col2` |

## Data Cleaning & Transformation

| Function | What It Does | Key Parameters |
|---|---|---|
| `clean_data()` | Handle missing values, drop duplicates, encode categoricals | `dataset_name`, `handle_missing`, `drop_duplicates` |
| `handle_outliers_iqr()` | Cap or remove outliers using IQR method | `dataset_name`, `columns`, `action` |
| `rename_columns()` | Rename columns | `dataset_name`, `rename_map` |
| `convert_column_types()` | Change column data types | `dataset_name`, `type_map` |

## Merging Datasets

| Function | What It Does | Key Parameters |
|---|---|---|
| `merge_datasets()` | General merge (any join type) | `left_name`, `right_name`, `on`, `how` |
| `merge_left()` | Left join | `left_name`, `right_name`, `on` |
| `merge_right()` | Right join | `left_name`, `right_name`, `on` |
| `merge_inner()` | Inner join | `left_name`, `right_name`, `on` |
| `merge_outer()` | Outer join | `left_name`, `right_name`, `on` |

## Visualization

| Function | What It Does | Key Parameters |
|---|---|---|
| `create_visualization()` | Bar, scatter, histogram, box, heatmap, line, etc. | `dataset_name`, `viz_type`, `x_column`, `y_column`, `title` |

Supported `viz_type` values: `bar`, `scatter`, `histogram`, `box`, `line`, `correlation_heatmap`, `pairplot`, `countplot`

## Unsupervised Learning

| Function | What It Does | Key Parameters |
|---|---|---|
| `perform_pca()` | Principal Component Analysis | `dataset_name`, `n_components`, `features` |
| `perform_elbow_analysis()` | Elbow plot for choosing k | `dataset_name`, `features`, `max_k` |
| `perform_kmeans_clustering()` | k-Means clustering | `dataset_name`, `n_clusters`, `features` |
| `perform_hierarchical_clustering()` | Hierarchical clustering with dendrogram | `dataset_name`, `n_clusters`, `features`, `linkage_method` |

## Train/Test Split

| Function | What It Does | Key Parameters |
|---|---|---|
| `split_data()` | Split into train/validation/test | `dataset_name`, `target_column`, `train_size`, `validation_size`, `test_size` |

**Always call `split_data()` before any supervised model training.**

## Supervised Learning — Classification & Regression

| Function | What It Does | Key Parameters |
|---|---|---|
| `train_linear_regression()` | Linear regression | `splits_name` |
| `train_logistic_regression()` | Logistic regression | `splits_name`, `max_iter` |
| `train_knn_classifier()` | k-Nearest Neighbors | `splits_name`, `n_neighbors` |
| `train_decision_tree()` | Decision tree (classification or regression) | `splits_name`, `max_depth`, `task_type` |
| `train_neural_network()` | Neural network (MLP) | `splits_name`, `hidden_layer_sizes`, `task_type` |
| `train_random_forest()` | Random forest | `splits_name`, `n_estimators`, `task_type` |
| `train_gradient_boosting()` | Gradient boosting (sklearn) | `splits_name`, `n_estimators`, `task_type` |
| `train_xgboost()` | XGBoost (with automatic fallback) | `splits_name`, `n_estimators`, `task_type` |

## Model Evaluation

| Function | What It Does | Key Parameters |
|---|---|---|
| `evaluate_classifier_performance()` | Confusion matrix, ROC curve, metrics | `model_name`, `splits_name` |
| `compare_models()` | Side-by-side comparison table | `model_names` (list), `splits_name` |

## Text Analytics

| Function | What It Does | Key Parameters |
|---|---|---|
| `perform_sentiment_analysis()` | Sentiment polarity and subjectivity | `dataset_name`, `text_column` |
| `create_bag_of_words()` | Bag-of-words feature matrix | `dataset_name`, `text_column`, `max_features` |
| `create_tfidf_features()` | TF-IDF feature matrix | `dataset_name`, `text_column`, `max_features` |
| `train_naive_bayes_text_classifier()` | Naive Bayes on text features | `dataset_name`, `text_column`, `target_column` |

## Web Scraping

| Function | What It Does | Key Parameters |
|---|---|---|
| `scrape_web_table()` | Scrape an HTML table from a URL | `url`, `table_index` |

## Utility

| Function | What It Does | Key Parameters |
|---|---|---|
| `save_dataset_to_excel()` | Export a dataset to Excel | `dataset_name`, `output_path`, `sheet_name` |
| `execute_python_code()` | Run arbitrary Python (escape hatch) | `code`, `description` |
