# Multi Output Emotion Regression
Development and comparison of various machine learning models for predicting multiple emotional scores of a person experiencing video content within a virtual reality headset.

Problem Statement:
We propose the development of a multi-output linear regression model that is capable of detecting 5 emotional scores of a user (Joy, Happy, Calmness, Relaxation, and Anger) at a given moment, based on the Electrocardiogram (ECG) and Galvanic Skin Response (GSR) physiological data. Existing approaches often tend to strictly classify emotions based on a classification score and uses the maximum values from multiple, independent, single-linear regression models to output multiple emotions. These approaches often fail to capture the variability of emotions, which can be dynamic and rapidly changing. However, human emotions are complex and dynamic, and a person can experience multiple emotions simultaneously or in rapid succession, depending on the situation and individual differences. For instance, a person can feel happy and excited while also feeling anxious and nervous about an upcoming event, or feel both love and anger towards a person at the same time. Therefore, a multi-output regression model that outputs scores of  multiple emotions simultaneously, with varying degrees of intensity, is more in line with how emotions are experienced in everyday life. Such a model is also capable of providing a more accurate and pragmatic representation of the emotional experiences.

Models Developed: RandomForest | MultiLayerPerceptron | Lasso Regressor | LightGBM | XGBoost | LSTM


GDrive Dataset Link: https://drive.google.com/drive/folders/1uHrLQJl-cXOJkYkPVhbpCQBaqnkx7si_?usp=sharing
