# 🚀 AI-Based Multi-Camera Person & Object Tracking System

An intelligent real-time surveillance system that detects, tracks, and identifies individuals across multiple camera feeds using advanced computer vision and deep learning techniques.

---

## 🎯 Key Highlights

* 🔍 Real-time object detection using YOLOv8
* 🧠 Robust tracking with DeepSORT (ID persistence)
* 😀 Face recognition (Known vs Unknown classification)
* 🎥 Multi-camera stream handling
* ⚡ Optimized performance with FPS monitoring
* 🔐 Secure authentication using JWT
* 🌐 Full-stack system (FastAPI + React)

---

## 🧠 System Architecture

Camera Feed → YOLOv8 Detection → DeepSORT Tracking → Face Recognition → API → Frontend Dashboard

---

## 🛠 Tech Stack

| Layer     | Technology                     |
| --------- | ------------------------------ |
| Backend   | FastAPI                        |
| Frontend  | React                          |
| AI Models | YOLOv8, DeepSORT, FaceNet      |
| Auth      | JWT                            |
| Storage   | Local embeddings (face_db.pkl) |

---

## ⚙️ Installation & Setup

```bash
git clone https://github.com/your-username/smart-ai-surveillance.git
cd smart-ai-surveillance

# Install dependencies
pip install -r requirements.txt

# Run backend
python backend/app/main.py
```

---

## 📸 Features Demo

* 🎯 Real-time tracking with unique IDs
* 🧍 Person re-identification across frames
* 😀 Known faces labeled with names
* ❓ Unknown faces detected separately

---

## 📈 Performance

* Real-time processing (~XX FPS depending on hardware)
* Lightweight and modular architecture

---

## 🚧 Future Enhancements

* ☁️ Cloud deployment (AWS/GCP)
* 🗄 Database integration
* 🚨 Smart alert system (intrusion detection)
* 📱 Mobile app integration

---

## 👨‍💻 Team

This project was developed by:

**Shivam and Team**

---

## 🤝 Contributions

This was a collaborative effort involving system design, AI model integration, backend development, and frontend implementation.

---

## ⭐ Support

If you found this project useful, consider giving it a ⭐ on GitHub!
