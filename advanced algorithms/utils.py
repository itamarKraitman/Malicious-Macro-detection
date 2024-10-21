# -*- coding: utf-8 -*-
"""Utils.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1lXg8T02ShEX294D70tCNCl8j2NWYJupU
"""

# from google.colab import drive
# drive.mount('/content/drive')

# Commented out IPython magic to ensure Python compatibility.
# %cd /content/drive/MyDrive/Colab Notebooks/Malicious Macro Detection
# %ls

# !pip install torch torchvision gensim

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from transformers import RobertaModel, RobertaTokenizer, RobertaConfig, AdamW, get_linear_schedule_with_warmup
from gensim.models import Word2Vec
from transformers import TextDataset
import numpy as np
import pandas as pd
from joblib import dump
import pickle

from sklearn.metrics import confusion_matrix, precision_score, recall_score, f1_score

class TextDataset(Dataset):
  def __init__(self, texts, labels, word2vec_model):
    self.texts = texts
    self.labels = labels
    self.word2vec_model = word2vec_model
    self.max_len = max(len(text.split()) for text in texts)

  def __len__(self):
    return len(self.texts)

  def __getitem__(self, idx):
    text = self.texts[idx].split()
    label = self.labels[idx]
    text_vector = np.zeros((self.max_len, self.word2vec_model.vector_size))

    for i, word in enumerate(text):
      if word in self.word2vec_model.wv:
        text_vector[i] = self.word2vec_model.wv[word]

    return torch.tensor(text_vector, dtype=torch.float32), torch.tensor(label, dtype=torch.long)

class CNNClassifier(nn.Module):
    def __init__(self, embed_dim, num_classes):
        super(CNNClassifier, self).__init__()
        self.conv1 = nn.Conv2d(in_channels=1, out_channels=100, kernel_size=(3, embed_dim))
        self.conv2 = nn.Conv2d(in_channels=1, out_channels=100, kernel_size=(4, embed_dim))
        self.conv3 = nn.Conv2d(in_channels=1, out_channels=100, kernel_size=(5, embed_dim))
        self.dropout = nn.Dropout(0.5)
        self.fc = nn.Linear(300, num_classes)

    def forward(self, x):
        x = x.unsqueeze(1)  # Add channel dimension
        conv1 = torch.relu(self.conv1(x)).squeeze(3)
        conv2 = torch.relu(self.conv2(x)).squeeze(3)
        conv3 = torch.relu(self.conv3(x)).squeeze(3)

        pool1 = torch.max_pool1d(conv1, conv1.size(2)).squeeze(2)
        pool2 = torch.max_pool1d(conv2, conv2.size(2)).squeeze(2)
        pool3 = torch.max_pool1d(conv3, conv3.size(2)).squeeze(2)

        out = torch.cat((pool1, pool2, pool3), 1)
        out = self.dropout(out)
        out = self.fc(out)

        return out

class CNNTrainer:
    def __init__(self, model, train_loader, validation_loader, test_loader, criterion, optimizer, device):
        self.model = model
        self.train_loader = train_loader
        self.validation_loader = validation_loader
        self.test_loader = test_loader
        self.criterion = criterion
        self.optimizer = optimizer
        self.device = device
        self.model.to(self.device)

    def train_epoch(self):
        self.model.train()
        epoch_loss = 0
        for texts, labels in self.train_loader:
            texts, labels = texts.to(self.device), labels.to(self.device)
            outputs = self.model(texts)
            loss = self.criterion(outputs, labels)

            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()
            epoch_loss += loss.item()

        return epoch_loss / len(self.train_loader)

    def evaluate(self, loader):
        self.model.eval()
        correct = 0
        total = 0
        all_labels = []
        all_predictions = []

        with torch.no_grad():
            for texts, labels in loader:
                texts, labels = texts.to(self.device), labels.to(self.device)
                outputs = self.model(texts)
                _, predicted = torch.max(outputs.data, 1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()

                all_labels.extend(labels.cpu().numpy())
                all_predictions.extend(predicted.cpu().numpy())

        accuracy = 100 * correct / total
        conf_matrix = confusion_matrix(all_labels, all_predictions)

        precision = precision_score(all_labels, all_predictions)
        recall = recall_score(all_labels, all_predictions)
        f1_scores = f1_score(all_labels, all_predictions)

        return accuracy, conf_matrix, precision, recall, f1_scores


    def train(self, num_epochs):
        for epoch in range(num_epochs):
            train_loss = self.train_epoch()
            validation_accuracy, conf_matrix, precision, recall, f1_score = self.evaluate(self.validation_loader)

            print(f'Epoch [{epoch+1}/{num_epochs}], Loss: {train_loss:.4f}, Validation Accuracy: {validation_accuracy:.2f}%, Precision: {precision}, Recall: {recall}, F1-score: {f1_score}')

        return validation_accuracy, conf_matrix, precision, recall, f1_score

    def test(self):
        test_accuracy, conf_matrix, precision, recall, f1_score = self.evaluate(self.test_loader)
        print(f'Test Accuracy: {test_accuracy:.2f}%, Precision: {precision}, Recall: {recall}, F1-score: {f1_score}')
        return test_accuracy, conf_matrix, precision, recall, f1_score

class LSTMModel(nn.Module):
    def __init__(self, input_dim, hidden_dim, vocab_size, output_dim):
        super(LSTMModel, self).__init__()
        # self.lstm = nn.LSTM(input_dim, hidden_dim, batch_first=True)
        # self.fc = nn.Linear(hidden_dim, output_dim)
        # self.hidden_dim = hidden_dim
        # self.dropout = nn.Dropout(0.5)
        self.batch_size = 32
        self.hidden_dim = hidden_dim
        self.LSTM_layers = 2
        self.input_size = input_dim # embedding dimention
        
        self.dropout = nn.Dropout(0.5)
        # self.embedding = nn.Embedding(self.input_size, self.hidden_dim, padding_idx=0)
        self.lstm = nn.LSTM(input_size=self.hidden_dim, hidden_size=self.hidden_dim, num_layers=self.LSTM_layers, batch_first=True)
        self.fc1 = nn.Linear(in_features=self.hidden_dim, out_features=257)
        self.fc2 = nn.Linear(257, 1)


    def forward(self, x):
        # out, _ = self.lstm(x)
        # out = self.fc(out[:, -1, :])
        # out = F.log_softmax(out, dim=1)
        # return out

        h = torch.zeros((self.LSTM_layers, x.size(0), self.hidden_dim)).to(x.device)
        c = torch.zeros((self.LSTM_layers, x.size(0), self.hidden_dim)).to(x.device)
        
        torch.nn.init.xavier_normal_(h)
        torch.nn.init.xavier_normal_(c)

        out, _ = self.lstm(x, (h,c))
        out = self.dropout(out)
        out = torch.relu_(self.fc1(out[:,-1,:]))
        out = self.dropout(out)
        out = torch.sigmoid(self.fc2(out))

        return out

class lstmTrainer:
    def __init__(self, model, train_loader, validation_loader, test_loader, criterion, optimizer, device):
        self.device = device
        self.model = model.to(device)
        self.train_loader = train_loader
        self.val_loader = validation_loader
        self.test_loader = test_loader
        self.criterion = criterion
        self.optimizer = optimizer

    def train_one_epoch(self):
        self.model.train()
        running_loss = 0.0
        all_preds = []
        all_labels = []

        for inputs, labels in self.train_loader:
            inputs, labels = inputs.to(self.device), labels.to(self.device)
            self.optimizer.zero_grad()
            outputs = self.model(inputs)
            loss = self.criterion(outputs, labels)
            loss.backward()
            self.optimizer.step()
            running_loss += loss.item()

            preds = torch.argmax(outputs, dim=1)
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

        avg_loss = running_loss / len(self.train_loader)
        precision = precision_score(all_labels, all_preds, average='macro')
        recall = recall_score(all_labels, all_preds, average='macro')
        f1 = f1_score(all_labels, all_preds, average='macro')
        conf_matrix = confusion_matrix(all_labels, all_preds)

        return avg_loss, precision, recall, f1, conf_matrix

    def evaluate(self, loader):
        self.model.eval()
        all_preds = []
        all_labels = []

        with torch.no_grad():
            correct = 0
            total = 0
            for inputs, labels in loader:
                inputs, labels = inputs.to(self.device), labels.to(self.device)
                outputs = self.model(inputs)
                predicted = torch.argmax(outputs, dim=1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()
                all_preds.extend(predicted.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())

        precision = precision_score(all_labels, all_preds)
        recall = recall_score(all_labels, all_preds)
        f1 = f1_score(all_labels, all_preds)
        conf_matrix = confusion_matrix(all_labels, all_preds)
        accuracy = 100 * correct / total

        return accuracy, precision, recall, f1, conf_matrix

    def train(self, num_epochs=30):
        for epoch in range(num_epochs):
            train_loss, precision, recall, f1, conf_matrix = self.train_one_epoch()
            validation_accuracy, precision, recall, f1_score, conf_matrix = self.evaluate(self.val_loader)

            print(f'Epoch [{epoch+1}/{num_epochs}], Loss: {train_loss}, Validation Accuracy: {validation_accuracy}, Precision: {precision}, Recall: {recall}, F1-score: {f1_score}')

        return validation_accuracy, conf_matrix, precision, recall, f1_score

    def test(self):
        test_accuracy, precision, recall, f1_score, conf_matrix, = self.evaluate(self.test_loader)
        print(f'Test Accuracy: {test_accuracy:.2f}, Precision: {precision}, Recall: {recall}, F1-score: {f1_score}')
        return test_accuracy, precision, recall, f1_score, conf_matrix

class RobertaClassifier(nn.Module):
    def __init__(self, num_classes=2):
        super(RobertaClassifier, self).__init__()
        self.roberta = RobertaModel.from_pretrained('roberta-base')
        self.dropout = nn.Dropout(0.3)
        self.classifier = nn.Linear(self.roberta.config.hidden_size, num_classes)

    def forward(self, input_ids, attention_mask):
        outputs = self.roberta(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = outputs[1]
        pooled_output = self.dropout(pooled_output)
        logits = self.classifier(pooled_output)
        return logits

class RobertaClassifierTrainer:
    def __init__(self, train_loader, val_loader, test_loader, optimizer, criterion ,epochs=10, lr=0.0001, device=None):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = RobertaClassifier().to(self.device)
        self.tokenizer = RobertaTokenizer.from_pretrained('roberta-base')
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.test_loader = test_loader
        self.optimizer = optimizer
        self.criterion = criterion
        self.epochs = epochs
        self.lr = lr
        self.scheduler = None

    def tokenize_batch(self, batch_texts):
        encoding = self.tokenizer.batch_encode_plus(
            batch_texts,
            max_length=128,
            padding=True,
            truncation=True,
            return_tensors='pt'
        )
        return encoding['input_ids'], encoding['attention_mask']

    def train_one_epoch(self):
        self.model.train()
        total_loss = 0

        for texts, labels in self.train_loader:
            input_ids, attention_mask = self.tokenize_batch(texts)
            input_ids = input_ids.to(self.device)
            attention_mask = attention_mask.to(self.device)
            labels = labels.to(self.device)

            self.model.zero_grad()

            logits = self.model(input_ids, attention_mask)

            loss = self.criterion(logits, labels)
            total_loss += loss.item()

            loss.backward()
            self.optimizer.step()
            self.scheduler.step()

        avg_loss = total_loss / len(self.train_loader)
        print(f"Training loss: {avg_loss:.4f}")

    def evaluate(self, data_loader):
        self.model.eval()
        total_loss = 0
        correct_predictions = 0
        all_preds = []
        all_labels = []

        with torch.no_grad():
            for texts, labels in data_loader:
                input_ids, attention_mask = self.tokenize_batch(texts)
                input_ids = input_ids.to(self.device)
                attention_mask = attention_mask.to(self.device)
                labels = labels.to(self.device)

                logits = self.model(input_ids, attention_mask)

                loss = self.criterion(logits, labels)
                total_loss += loss.item()

                preds = torch.argmax(logits, dim=1)
                correct_predictions += torch.sum(preds == labels)

                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())

        avg_loss = total_loss / len(data_loader)
        accuracy = correct_predictions.double() / len(data_loader.dataset)
        precision = precision_score(labels.cpu().numpy(), preds.cpu().numpy())
        recall = recall_score(labels.cpu().numpy(), preds.cpu().numpy())
        f1 = f1_score(labels.cpu().numpy(), preds.cpu().numpy())
        conf_matrix = confusion_matrix(all_labels, all_preds)

        return avg_loss, accuracy, precision, recall, f1, conf_matrix

    def train(self):
        total_steps = len(self.train_loader) * self.epochs
        self.scheduler = get_linear_schedule_with_warmup(self.optimizer, num_warmup_steps=0, num_training_steps=total_steps)

        for epoch in range(self.epochs):
            print(f"Epoch {epoch + 1}/{self.epochs}")
            self.train_one_epoch()

            val_loss, val_accuracy, precision, recall, f1_score, conf_matrix = self.evaluate(self.val_loader)
            print(f"Validation loss: {val_loss:.4f}, Validation accuracy: {val_accuracy:.4f}, Precision: {precision}, Recall: {recall}, F1-score: {f1_score}")

    def test(self):
        test_loss, test_accuracy, precision, recall, f1_score, conf_matrix = self.evaluate(self.test_loader)
        print(f"Test loss: {test_loss:.4f}, Test accuracy: {test_accuracy:.4f}, Precision: {precision}, Recall: {recall}, F1-score: {f1_score}")
        return test_loss, test_accuracy, precision, recall, f1_score

# mapper = {
#     'white' : 1,
#     'mal' : 0
# }

# train_set = pd.read_csv('train_dataset.csv', encoding='utf-16le')
# val_set = pd.read_csv('validation_dataset.csv', encoding='utf-16le')
# test_set = pd.read_csv('test_dataset.csv', encoding='utf-16le')

# x_train, y_train = train_set['vba_code'], train_set['label']
# x_val, y_val = val_set['vba_code'], val_set['label']
# x_test, y_test = test_set['vba_code'], test_set['label']

# y_train = y_train.map(mapper)
# y_val = y_val.map(mapper)
# y_test = y_test.map(mapper)

"""### Preparing the data"""

# all_texts = pd.concat([x_train, x_val, x_test]).tolist()
# word2vec_model = Word2Vec([text.split() for text in all_texts], vector_size=100, window=5, min_count=1, workers=4)

# train_dataset = TextDataset(x_train.tolist(), y_train.tolist(), word2vec_model)
# validation_dataset = TextDataset(x_val.tolist(), y_val.tolist(), word2vec_model)
# test_dataset = TextDataset(x_test.tolist(), y_test.tolist(), word2vec_model)

# train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
# validation_loader = DataLoader(validation_dataset, batch_size=32)
# test_loader = DataLoader(test_dataset, batch_size=32)

# loaders_paths = {
#     '/content/drive/MyDrive/Colab Notebooks/Malicious Macro Detection/train_loader.joblib': train_loader,
#     '/content/drive/MyDrive/Colab Notebooks/Malicious Macro Detection/val_loader.joblib' : validation_loader,
#     '/content/drive/MyDrive/Colab Notebooks/Malicious Macro Detection/test_loader.joblib' : test_loader,
#     '/content/drive/MyDrive/Colab Notebooks/Malicious Macro Detection/word2vec_model.joblib' : word2vec_model
#      }


def save_loader(path, loader):
    try:
      dump(loader, path)
      print(f"{loader} saved sucessfuly")
    except Exception as e:
      print(f"error saving {loader} {e}")

# for path, loader in loaders_paths.items():
#   save_loader(path, loader)

