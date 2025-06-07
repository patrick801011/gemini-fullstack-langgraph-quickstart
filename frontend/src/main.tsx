import React, { StrictMode, Suspense } from "react"; // Added Suspense
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./global.css";
import App from "./App.tsx";
import i18n from "./i18n"; // Import i18n instance
import { I18nextProvider } from "react-i18next"; // Import I18nextProvider

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Suspense fallback="Loading..."> {/* Added Suspense */}
      <I18nextProvider i18n={i18n}> {/* Added I18nextProvider */}
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </I18nextProvider>
    </Suspense>
  </StrictMode>
);
