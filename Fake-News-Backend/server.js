const fetch = require("node-fetch");
const express = require("express");
const cors = require("cors");

const app = express();
app.use(cors());
app.use(express.json());

// Temporary data (instead of MongoDB)
let newsData = [];

// Home route
app.get("/", (req, res) => {
  res.send("Fake News Detection API Running...");
});

// Add news
app.post("/add-news", (req, res) => {
  const { title, content } = req.body;

  const newNews = {
    id: newsData.length + 1,
    title,
    content
  };

  newsData.push(newNews);

  res.json({
    message: "News added successfully",
    data: newNews
  });
});

// Get all news
app.get("/news", (req, res) => {
  res.json(newsData);
});

app.get("/history", (req, res) => {
  res.json(newsData);
});

app.post("/predict", (req, res) => {
  const { text } = req.body;

  const patterns = [
    { regex: /100%|guaranteed|miracle/i, weight: 3 },
    { regex: /shocking|breaking|unbelievable/i, weight: 2 },
    { regex: /click here|share now|forward this/i, weight: 2 },
    { regex: /aliens|conspiracy|secret government/i, weight: 3 },
    { regex: /cure cancer instantly/i, weight: 4 }
  ];

  let score = 0;
  let reasons = [];

  patterns.forEach(p => {
    if (p.regex.test(text)) {
      score += p.weight;
      reasons.push(p.regex.toString());
    }
  });

  let result, confidence;

  if (score >= 4) {
    result = "FAKE NEWS";
    confidence = Math.min(60 + score * 5, 95);
  } else {
    result = "REAL NEWS";
    confidence = Math.max(60 - score * 5, 50);
  }

  const response = {
    result,
    confidence: confidence + "%",
    explanation:
      reasons.length > 0
        ? "Suspicious patterns: " + reasons.join(", ")
        : "No suspicious patterns detected"
  };

  // Save history
  newsData.push({
    text,
    ...response,
    date: new Date()
  });

  res.json(response);
});

app.delete("/history", (req, res) => {
  newsData = [];
  res.json({ message: "History cleared" });
});

// Start server
app.listen(5000, () => {
  console.log("Server running on port 5000");
});