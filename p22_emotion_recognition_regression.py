# -*- coding: utf-8 -*-
"""P22_emotion recognition_regression.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1NK6XjIkw5cCqAH04rmT3-hEeyKqIiNmz

# Multi-Output Regression for Emotion Prediction
Antony John Edathattil - aedatha@ncsu.edu

Hritwik Shukla - hshukla@ncsu.edu

Sahil Palarpwar - spalarp@ncsu.edu

Link to Dataset: [https://github.com/antonyjohne/MultiOutputEmotionRegression](https://github.com/antonyjohne/MultiOutputEmotionRegression)
"""

!pip install tsfresh

"""
Connect to a TPU runtime in Google Colab to train the LSTM model
Runtime --> Change Runtime Type --> Select TPU
"""

import tensorflow as tf
try:
  tpu = tf.distribute.cluster_resolver.TPUClusterResolver()  # TPU detection
  print('Running on TPU ', tpu.cluster_spec().as_dict()['worker'])
except ValueError:
  raise BaseException('ERROR: Not connected to a TPU runtime')

tf.config.experimental_connect_to_cluster(tpu)
tf.tpu.experimental.initialize_tpu_system(tpu)
tpu_strategy = tf.distribute.TPUStrategy(tpu)

# Commented out IPython magic to ensure Python compatibility.
"""
Mount your Drive and initialize the data paths
Ensure the dataset in within the folder named "Dataset" and the program is within
the home directory outside the Dataset folder
"""

from google.colab import drive

drive.mount('/content/drive/')
# %cd /content/drive/MyDrive/Alda/Dataset

import os
import pickle
import numpy as np
import pandas as pd
import seaborn as sb
import tsfresh as ts
import matplotlib.pyplot as plt
from tsfresh.feature_extraction import MinimalFCParameters, EfficientFCParameters

import lightgbm as lgb
from keras import optimizers
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
from sklearn.decomposition import PCA
from keras.models import Model, Sequential
from sklearn.neural_network import MLPRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression, Lasso
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from keras.layers import Input, Flatten, Dense, Dropout, LSTM, Bidirectional
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

"""
Data Format:
•	Data = [13, 2, ?] 
  - First dimension (12) = Number of videos
  - Second dimension (2) = Number of Channels -	Channels = [GSR, ECG]
  - Third dimension (?) = Length of Data 
"""


signal_path = os.getcwd()+"/05 ECG-GSR Data/01 ECG-GSR Data (Pre-Processed)"
scores_path = os.getcwd()+"/03 Self-Reported Questionnaires"
os.makedirs(os.getcwd()+f"/ProcessedData", exist_ok=True)
os.makedirs(os.getcwd()+f"/FeatureData", exist_ok=True)

processed_data_path = os.getcwd()+'/ProcessedData'
sampled_data_dir = os.getcwd()+'/FeatureData'

score_df = pd.read_excel(scores_path + "/02 Post Exposure Ratings.xlsx")
score_labels = score_df.columns[9:14]

"""
Read each subject --> Check for bad data -->  Extract 120 sec of signal data
Convert Raw Data to DataFrame and export as file with name "SubID_VideoID.csv"
"""

def x_dataloader(num_subjects):

  os.makedirs(os.getcwd()+f"/ProcessedData", exist_ok=True)
  signal_file_list = os.listdir(signal_path)
  print("Data Preprocessing has begun. This might take a while...!\n")

  for sub in range(num_subjects):
    if sub == 6 or sub == 26: #Bad Subject Data
      continue

    filename = signal_path + '/' + signal_file_list[sub]

    with open(filename,  'rb')  as  subject_file:
      data = pickle.Unpickler(subject_file).load()

      for vid_num in range(12):
        try:
          signal_df = pd.DataFrame(np.array(data["Data"][vid_num][:120000]), columns=['GSR', 'ECG'])
          signal_df.insert(0, 'time', np.arange(0.001, 120.0001, 0.001), allow_duplicates=True)
          signal_df.insert(0, 'id', sub+101, allow_duplicates=True)
          signal_df.insert(1, 'vid_num', vid_num+1, allow_duplicates=True)
          signal_df.fillna(0.0, inplace=True)
          signal_df.to_csv(f"{os.getcwd()}/ProcessedData/{sub+101}_V{vid_num+1}.csv", header=True, index=False)
        
        except IndexError as e:
          print(f"\nError while Processing Subject {sub}, Video {vid_num}")
    print(f"Subject {sub} Data Preprocessed Successfully!")
  print("\nData Preprocessed Successfully!\n")

"""
Create feature windows for Time series data every 4 sec --> Extract Statistical Features of window
Export features per subject per vido into folder "FeatureData"
"""

def feature_engineering(window_size=4000, step_size=4000, parameter_set=MinimalFCParameters(), param_set_name='Minimal'):

  # Define the path to the directory where the CSV files are stored
  storage_path = sampled_data_dir+f"/{param_set_name}"
  os.makedirs(storage_path, exist_ok=True)

  # Loop through all the CSV files in the directory
  for filename in os.listdir(processed_data_path):
      if filename.endswith(".csv"):
          # Read the CSV file using pandas
          df = pd.read_csv(os.path.join(processed_data_path, filename))

          for j in range(0, df.shape[0] - window_size, step_size):
              temp_list = df.iloc[j: j + window_size, :]

              window_filename = f"{filename[:-4]}_sampled.csv"

              extracted_features_df = ts.extract_features(temp_list, column_id='id', column_sort='time', default_fc_parameters = parameter_set)
              extracted_features_df.to_csv(storage_path+'/'+window_filename, index=False, mode='a', header=not os.path.exists(storage_path+'/'+window_filename))

  print("Features have been Engineered into folder 'Feature Data'")
  return os.listdir(sampled_data_dir)

"""
Read 5 emotion score labels for each SubID_VidID and match to Feature Windows
Create a complete dataset with Features & Labels and export
"""
def final_dataset_compiler(param_set_name):
    temp_feature_list = []
    storage_path = sampled_data_dir+f"/{param_set_name}"

    feature_file_list = os.listdir(storage_path)

    for i, feature_file in enumerate(feature_file_list):
      filename_split = feature_file.split("_")
      subject_id, vid_num = int(filename_split[0]), int(filename_split[1][1:])

      filename = os.path.join(storage_path, feature_file)
      temp_df = pd.read_csv(filename)
      emotion_scores = score_df[(score_df["ID"]==subject_id) & (score_df["Num_Code"]==vid_num)][score_labels]

      for label in emotion_scores.columns:
        temp_df.insert(temp_df.shape[1], str(label), float(emotion_scores[label]), allow_duplicates=True)

      temp_feature_list.append(temp_df)

    df = pd.concat(temp_feature_list)
    df = df.dropna()
    df.to_csv(f"FinalDataset_{param_set_name}.csv", header=True)
    print(f"{param_set_name} Dataset Shape: {df.shape}\n")

def metric_calc(y_pred, y_true):
    mae =  mean_absolute_error(y_true, y_pred)
    rmse = mean_squared_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    print(f"Metrics:\n   MAE: {mae}   |   MSE: {rmse}   |   R2:{r2}\n")
    return mae, rmse, r2

def feature_selection(x, plots=True, num_feat=2):
    pca = PCA()
    x_pca = pca.fit_transform(x)
    features = range(pca.n_components_)
    if plots:
        plt.figure(figsize=(6, 3))
        plt.bar(features, pca.explained_variance_)
        plt.xlabel('PCA feature')
        plt.ylabel('Variance')
        plt.xticks(features)
        plt.show()
    pca = PCA(n_components=num_feat)
    x_pruned = pca.fit_transform(x)
    return x_pruned

def LSTM_feature_engineering(window_size=4000, step_size=4000):
    """
    Create 4 sec signal windows of features & classes using processed dataset
    Transform into LSTM input shape: (samples, timesteps, features)
    """
    x_data, y_data = [], []

    for filename in os.listdir(processed_data_path):
        if filename.endswith(".csv"):
            df = pd.read_csv(os.path.join(processed_data_path, filename))
            standard_df = StandardScaler().fit_transform(df.loc[:,['GSR','ECG']])
            for j in range(0, df.shape[0] - window_size, step_size):
                temp_list = standard_df[j: j + window_size]
                temp_labels = score_df[(score_df["ID"]==df['id'][0]) & (score_df["Num_Code"]==df['vid_num'][0])][score_labels]
                x_data.append(temp_list)
                y_data.append(temp_labels)

    print("\nFeatures have been windowed into the correct shape for LSTM input.\n")
    return np.array(x_data), np.array(y_data)


def LRegression(x_train, y_train):
    print("\nLasso Regressor...\nFitting Model. Please Wait...")
    lmodel = Lasso(random_state=1306)
    lmodel.fit(x_train, y_train)
    print("STATUS - Model Fit Complete")
    return lmodel


def RFRegression(x_train, y_train):
    print("\nRandom Forest Regressor...\nFitting Model. Please Wait...")
    rfmodel = RandomForestRegressor(max_depth=10, random_state=1306)
    rfmodel.fit(x_train, y_train)
    print("STATUS - Model Fit Complete")
    return rfmodel

def MLPRegression(x_train, y_train):
    print("\nMLP Regressor...\nFitting Model. Please Wait...")
    mlpmodel = MLPRegressor(hidden_layer_sizes=(30,30,10), activation='relu', solver='adam', alpha=0.1, batch_size='auto', max_iter=1000, random_state=13)
    mlpmodel.fit(x_train, y_train)
    print("STATUS - Model Fit Complete")
    return mlpmodel

def LGBMRegression1(x_train, y_train):
    print("\nLightGBM Regressor 1...\nFitting Model. Please Wait...")
    lgbmmodel = MultiOutputRegressor(lgb.LGBMRegressor(num_leaves=100, max_depth=-1,n_estimators=200,learning_rate=0.01))
    lgbmmodel.fit(x_train, y_train)
    print("STATUS - Model Fit Complete")
    return lgbmmodel  
    
def LGBMRegression2(x_train, y_train):
    print("\nLightGBM Regressor 2...\nFitting Model. Please Wait...")
    lgbmmodel = MultiOutputRegressor(lgb.LGBMRegressor(num_leaves=200, max_depth=-1,n_estimators=100,learning_rate=0.05))
    lgbmmodel.fit(x_train, y_train)
    print("STATUS - Model Fit Complete")
    return lgbmmodel

def LGBMRegression3(x_train, y_train):
    print("\nLightGBM Regressor 3...\nFitting Model. Please Wait...")
    lgbmmodel = MultiOutputRegressor(lgb.LGBMRegressor(num_leaves=300, max_depth=-1,n_estimators=200,learning_rate=0.05))
    lgbmmodel.fit(x_train, y_train)
    print("STATUS - Model Fit Complete")
    return lgbmmodel  

def XGBRegression(x_train, y_train):
    print("\nXGBoost Regressor...\nFitting Model. Please Wait...")
    xgbmodel = XGBRegressor(booster='gbtree')
    xgbmodel.fit(x_train, y_train)
    print("STATUS - Model Fit Complete")
    return xgbmodel 

def LSTMRegression(x_train, y_train):
    print("\nLSTM Regressor...\nFitting Model. Please Wait...")
    with tpu_strategy.scope():
        model = Sequential()
        model.add(LSTM(8, input_shape=(x_train.shape[1],x_train.shape[2])))
        model.add(Dense(5))
        optimizer = optimizers.Adam(learning_rate=0.001)
        model.compile(loss='mse', optimizer=optimizer, metrics=['accuracy']) 
    model.fit(x_train, y_train, batch_size=16, epochs=10, verbose=1)
    print("STATUS - Model Fit Complete")
    return model

"""
Generate the final dataset to run models on if dataset doesn't exist
"""
if 'FinalDataset_Minimal.csv' not in os.list_dir(os.getcwd()):
    x_dataloader(34)
    feature_engineering(window_size=4000, step_size=4000, parameter_set=MinimalFCParameters(), param_set_name='Minimal')
    final_dataset_compiler(param_set_name='Minimal')

for i in range(2):

    if i==0:
        print("---------- MODEL STUDY USING MINIMAL DATASET ----------")
        df = pd.read_csv("FinalDataset_Minimal.csv")
        mask = df.applymap(lambda x: pd.to_numeric(x, errors='coerce')).isnull().any(axis=1)
        df = df[~mask]
        X, Y = df.iloc[:,:-5], df.iloc[:,-5:]

    elif i==1:
        print("\n\n---------- MODEL STUDY USING MINIMAL DATASET WITH PCA ----------")
        df = pd.read_csv("FinalDataset_Minimal.csv")
        mask = df.applymap(lambda x: pd.to_numeric(x, errors='coerce')).isnull().any(axis=1)
        df = df[~mask]
        X, Y = df.iloc[:,:-5], df.iloc[:,-5:]
        X = feature_selection(X, plots=True, num_feat=5)

    x_train, x_test, y_train, y_test = train_test_split(X, Y, test_size=0.2, random_state=13)
    print(f"X_Train Shape: {x_train.shape}, Y_Train Shape: {y_train.shape}, X_Test Shape: {x_test.shape}, Y_Test Shape:{y_test.shape}")
    scaler = StandardScaler().fit(x_train)
    x_train, x_test = scaler.transform(x_train), scaler.transform(x_test)

    models_dict= {'RF':RFRegression, 'MLP':MLPRegression, 'L':LRegression, 'LGBM1':LGBMRegression1, 
                  'LGBM2':LGBMRegression2, 'LGBM3':LGBMRegression3, 'XGB': XGBRegression, 'LSTM': LSTMRegression}

    for model_name in models_dict.keys():
        if model_name == 'LSTM':
            X , Y =  LSTM_feature_engineering(window_size=1000, step_size=1000)
            x_train, x_test, y_train, y_test = train_test_split(X, Y, test_size=0.2, random_state=13)

            x_train_og_shape, x_test_og_shape = x_train.shape, x_test.shape
            x_train, x_test = np.reshape(x_train, (x_train.shape[0], -1)), np.reshape(x_test, (x_test.shape[0], -1))

            scaler = StandardScaler().fit(x_train)
            x_train, x_test = scaler.transform(x_train), scaler.transform(x_test)

            x_train, x_test = np.reshape(x_train, (-1,x_train_og_shape[1],x_train_og_shape[2])),  np.reshape(x_test, (-1,x_test_og_shape[1],x_test_og_shape[2]))

        model = models_dict[model_name](x_train, y_train)
        y_pred = np.ceil(model.predict(x_test)).clip(min=0)
        mae, rmse, r2 = metric_calc(y_pred, y_test)