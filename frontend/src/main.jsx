import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./index.css";

const CHROME_ASYNC_MESSAGE_WARNING =
  "A listener indicated an asynchronous response by returning true, but the message channel closed before a response was received";

const isChromeAsyncMessageWarning = (value) => {
  const message = value?.message ?? String(value ?? "");
  return message.includes(CHROME_ASYNC_MESSAGE_WARNING);
};

window.addEventListener("unhandledrejection", (event) => {
  if (isChromeAsyncMessageWarning(event.reason)) {
    event.preventDefault();
  }
});

window.addEventListener("error", (event) => {
  if (isChromeAsyncMessageWarning(event.error) || isChromeAsyncMessageWarning(event.message)) {
    event.preventDefault();
  }
});

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
