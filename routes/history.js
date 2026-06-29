const express = require("express");
const router = express.Router();

// Temporary history
let history = [];

// Add history
router.post("/", (req, res) => {
  const { news } = req.body;

  history.push(news);

  res.json({ message: "Saved to history" });
});

// Get history
router.get("/", (req, res) => {
  res.json(history);
});

module.exports = router;