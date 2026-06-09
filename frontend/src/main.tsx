import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./index.css";
import { api } from "./lib/api";

// Fire-and-forget ping to wake up the backend (Render free tier cold starts).
// This runs as early as possible so by the time the user hits Login the
// backend is already warm.
api.get("/health").catch(() => undefined);

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
