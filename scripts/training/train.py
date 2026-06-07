# scripts/training/train.py
#!/usr/bin/env python3
"""Training script for plant disease classification model"""

import argparse
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import transforms, datasets
from pathlib import Path
import json
from tqdm import tqdm
import logging
from datetime import datetime
import random
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PlantDiseaseTrainer:
    """Trainer for plant disease classification"""
    
    def __init__(
        self,
        model_name: str = "mobilenetv3",
        num_classes: int = 15,
        learning_rate: float = 0.001,
        batch_size: int = 32,
        epochs: int = 50,
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
        class_names: list[str] | None = None,
        dataset_metadata: dict | None = None,
    ):
        self.model_name = model_name
        self.num_classes = num_classes
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.epochs = epochs
        self.device = device
        self.class_names = class_names or []
        self.dataset_metadata = dataset_metadata or {}
        
        # Initialize model
        self.model = self._create_model()
        self.criterion = nn.CrossEntropyLoss()
        self.optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode='min', patience=5, factor=0.5
        )
        
    def _create_model(self):
        """Create model architecture"""
        if self.model_name == "mobilenetv3":
            import torchvision.models as models
            try:
                weights = models.MobileNet_V3_Large_Weights.DEFAULT
                model = models.mobilenet_v3_large(weights=weights)
            except Exception as exc:
                logger.warning("Could not load pretrained MobileNetV3 weights: %s", exc)
                logger.warning("Falling back to randomly initialized MobileNetV3 weights.")
                model = models.mobilenet_v3_large(weights=None)
            
            # Replace classifier
            in_features = model.classifier[-1].in_features
            model.classifier = nn.Sequential(
                nn.Linear(in_features, 1024),
                nn.Hardswish(),
                nn.Dropout(0.2),
                nn.Linear(1024, self.num_classes)
            )
            return model.to(self.device)
        else:
            raise ValueError(f"Unsupported model: {self.model_name}")
    
    def train_epoch(self, train_loader):
        """Train for one epoch"""
        self.model.train()
        total_loss = 0
        correct = 0
        total = 0
        
        pbar = tqdm(train_loader, desc="Training")
        for images, labels in pbar:
            images, labels = images.to(self.device), labels.to(self.device)
            
            self.optimizer.zero_grad()
            outputs = self.model(images)
            loss = self.criterion(outputs, labels)
            loss.backward()
            self.optimizer.step()
            
            total_loss += loss.item()
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()
            
            pbar.set_postfix({
                'loss': total_loss / (pbar.n + 1),
                'acc': 100. * correct / total
            })
        
        return total_loss / len(train_loader), 100. * correct / total
    
    def validate(self, val_loader):
        """Validate model"""
        self.model.eval()
        total_loss = 0
        correct = 0
        total = 0
        
        with torch.no_grad():
            pbar = tqdm(val_loader, desc="Validation")
            for images, labels in pbar:
                images, labels = images.to(self.device), labels.to(self.device)
                outputs = self.model(images)
                loss = self.criterion(outputs, labels)
                
                total_loss += loss.item()
                _, predicted = outputs.max(1)
                total += labels.size(0)
                correct += predicted.eq(labels).sum().item()
                
                pbar.set_postfix({
                    'loss': total_loss / (pbar.n + 1),
                    'acc': 100. * correct / total
                })
        
        return total_loss / len(val_loader), 100. * correct / total
    
    def train(self, train_loader, val_loader, save_dir: Path):
        """Full training loop"""
        best_val_acc = 0
        
        for epoch in range(self.epochs):
            logger.info(f"\nEpoch {epoch+1}/{self.epochs}")
            
            # Train
            train_loss, train_acc = self.train_epoch(train_loader)
            
            # Validate
            val_loss, val_acc = self.validate(val_loader)
            
            # Update scheduler
            self.scheduler.step(val_loss)
            
            logger.info(
                f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.2f}% | "
                f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.2f}%"
            )
            
            # Save best model
            if val_acc > best_val_acc:
                best_val_acc = val_acc
                self.save_model(save_dir / "best_model.pth", epoch, val_acc)
                logger.info(f"Saved best model with accuracy: {val_acc:.2f}%")
    
    def save_model(self, path: Path, epoch: int, accuracy: float):
        """Save model checkpoint"""
        torch.save({
            'epoch': epoch,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'accuracy': accuracy,
            'model_name': self.model_name,
            'num_classes': self.num_classes,
            'class_names': self.class_names,
            'dataset_metadata': self.dataset_metadata,
        }, path)
        
        # Save metadata
        metadata = {
            'model_name': self.model_name,
            'num_classes': self.num_classes,
            'class_names': self.class_names,
            'accuracy': accuracy,
            'epoch': epoch,
            'training_date': datetime.utcnow().isoformat(),
            'dataset_metadata': self.dataset_metadata,
        }
        
        with open(path.parent / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Train plant disease detection model")
    parser.add_argument("--data_dir", type=str, required=True, help="Path to dataset")
    parser.add_argument("--model", type=str, default="mobilenetv3", help="Model architecture")
    parser.add_argument("--epochs", type=int, default=50, help="Number of epochs")
    parser.add_argument("--batch_size", type=int, default=32, help="Batch size")
    parser.add_argument("--lr", type=float, default=0.001, help="Learning rate")
    parser.add_argument("--output_dir", type=str, default="./models", help="Output directory")
    parser.add_argument("--num_workers", type=int, default=4, help="DataLoader worker count")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    
    # Data transforms
    train_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(15),
        transforms.ColorJitter(brightness=0.2, contrast=0.2),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    
    val_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    
    # Load datasets
    train_dataset = datasets.ImageFolder(
        Path(args.data_dir) / "train",
        transform=train_transform
    )
    val_dataset = datasets.ImageFolder(
        Path(args.data_dir) / "val",
        transform=val_transform
    )
    
    # Create data loaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers
    )
    
    logger.info(f"Training samples: {len(train_dataset)}")
    logger.info(f"Validation samples: {len(val_dataset)}")
    logger.info(f"Number of classes: {len(train_dataset.classes)}")

    metadata_path = Path(args.data_dir) / "metadata" / "dataset_card.json"
    dataset_metadata = {}
    if metadata_path.exists():
        with metadata_path.open("r", encoding="utf-8") as file:
            dataset_metadata = json.load(file)
    
    # Initialize trainer
    trainer = PlantDiseaseTrainer(
        model_name=args.model,
        num_classes=len(train_dataset.classes),
        learning_rate=args.lr,
        batch_size=args.batch_size,
        epochs=args.epochs,
        class_names=train_dataset.classes,
        dataset_metadata=dataset_metadata,
    )
    
    # Train model
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    trainer.train(train_loader, val_loader, output_dir)
    
    logger.info(f"Training completed! Model saved to {output_dir}")


if __name__ == "__main__":
    main()
