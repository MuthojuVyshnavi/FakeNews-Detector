const express = require("express");
const router = express.Router();

// Temporary users array
let users = [];

// Register
router.post("/register", (req, res) => {
  const { username, password } = req.body;

  users.push({ username, password });

  res.json({ message: "User registered successfully" });
});

// Login
router.post("/login", (req, res) => {
  const { username, password } = req.body;

  const user = users.find(
    (u) => u.username === username && u.password === password
  );

  if (user) {
    res.json({ message: "Login successful" });
  } else {
    res.status(401).json({ message: "Invalid credentials" });
  }
});

module.exports = router;