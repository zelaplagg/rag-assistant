# Lecture Notes: Machine Learning Basics

## What is machine learning?

Machine learning (ML) is a field of AI where a program learns patterns from data
instead of being explicitly programmed with rules. The goal is to make accurate
predictions or decisions on new, unseen data.

## Types of learning

- **Supervised learning:** the model learns from labeled examples (input → known
  output). Used for classification and regression.
- **Unsupervised learning:** the model finds structure in unlabeled data, e.g.
  clustering or dimensionality reduction.
- **Reinforcement learning:** an agent learns by trial and error, receiving rewards
  or penalties for its actions.

## Classification vs regression

- **Classification** predicts a category (e.g. healthy / faulty).
- **Regression** predicts a continuous number (e.g. remaining useful life in cycles).

## The training workflow

1. Collect and clean the data.
2. Split it into training and test sets.
3. Choose a model and train it on the training set.
4. Evaluate it on the test set using metrics like accuracy, precision, recall.
5. Tune hyperparameters and repeat.

## Overfitting and underfitting

- **Overfitting:** the model memorizes the training data and performs poorly on new
  data. Fixes: more data, regularization, simpler models, cross-validation.
- **Underfitting:** the model is too simple to capture the pattern. Fixes: a more
  expressive model or better features.

## Key evaluation metrics

- **Accuracy:** share of correct predictions.
- **Precision:** of the items predicted positive, how many were truly positive.
- **Recall:** of the truly positive items, how many were found.
- **ROC-AUC:** how well the model separates classes across thresholds.
