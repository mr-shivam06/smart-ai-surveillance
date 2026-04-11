# 🚀 AI-Based Multi-Camera Person & Object Tracking System

An advanced real-time surveillance system designed to detect, track, and identify individuals across multiple camera feeds using cutting-edge computer vision and deep learning techniques.

---

## 🌟 Overview

This project simulates an intelligent surveillance solution capable of:

* Detecting objects in real time
* Tracking individuals with persistent IDs
* Recognizing known faces and flagging unknown ones
* Managing multiple camera streams efficiently

It demonstrates practical implementation of AI in security, monitoring, and smart city applications.

---

## 🎯 Key Features

* 🔍 **Object Detection** — Powered by YOLOv8 for high-speed and accurate detection
* 🧠 **Multi-Object Tracking** — DeepSORT ensures consistent tracking IDs
* 😀 **Face Recognition** — Distinguishes between known and unknown individuals
* 🎥 **Multi-Camera Support** — Handles multiple video streams simultaneously
* ⚡ **Real-Time Performance** — Optimized pipeline with FPS monitoring
* 🔐 **Authentication System** — Secure endpoints using JWT
* 🌐 **Full-Stack Architecture** — FastAPI backend + React frontend

---

## 🧠 System Architecture

```text
Camera Feed → YOLOv8 → DeepSORT → Face Recognition → FastAPI → React Dashboard
```

---

## 🛠 Tech Stack

| Category       | Technology Used                |
| -------------- | ------------------------------ |
| Backend        | FastAPI                        |
| Frontend       | React                          |
| AI/ML Models   | YOLOv8, DeepSORT, FaceNet      |
| Authentication | JWT                            |
| Language       | Python, JavaScript             |
| Storage        | Local embeddings (face_db.pkl) |

---

## ⚙️ Installation & Setup

```bash
# Clone the repository
git clone https://github.com/mr-shivam06/smart-ai-surveillance.git

# Navigate to project folder
cd smart-ai-surveillance

# Install backend dependencies
pip install -r requirements.txt

# Run the backend server
python backend/app/main.py
```

---

## 📸 Features Demonstration

* 🎯 Real-time detection and tracking with unique IDs
* 🧍 Person re-identification across frames
* 😀 Known faces labeled with names
* ❓ Unknown individuals flagged separately

---

## 📊 Performance Insights

* ⚡ Real-time processing (~XX FPS depending on hardware)
* 🧩 Modular and scalable architecture
* 🧠 Efficient tracking and recognition pipeline

---

## 🚧 Future Enhancements

* ☁️ Cloud deployment (AWS / GCP)
* 🗄 Integration with databases (PostgreSQL / MongoDB)
* 🚨 Smart alert system (intrusion detection, notifications)
* 📱 Mobile app interface
* 📡 Edge device optimization

---

## 👨‍💻 Team

This project was developed by:

**Shivam and Team**

---

## 🤝 Contributions

This was a collaborative effort involving:

* System design
* AI model integration
* Backend API development
* Frontend interface design

---

## 💼 Use Cases

* 🏢 Smart Surveillance Systems
* 🚦 Traffic Monitoring
* 🏫 Campus Security
* 🏬 Retail Analytics
* 🏙 Smart City Infrastructure

---

## ⭐ Support & Feedback

If you found this project helpful or interesting, consider giving it a ⭐ on GitHub.
Feedback and suggestions are always welcome!

---

## 📬 Contact

For collaboration or queries:
📧 Reach out via GitHub profile

---
