import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, ProtectedRoute } from "./components/Auth";
import Layout from "./components/Layout";
import { LiveProvider } from "./components/Live";
import { ToastProvider } from "./components/Toasts";
import { LoginPage, RegisterPage } from "./pages/AuthPages";
import DashboardPage from "./pages/DashboardPage";
import DocumentPage from "./pages/DocumentPage";
import SearchPage from "./pages/SearchPage";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ToastProvider>
      <BrowserRouter>
        <AuthProvider>
          <LiveProvider>
            <Routes>
              <Route path="login" element={<LoginPage />} />
              <Route path="register" element={<RegisterPage />} />
              <Route element={<ProtectedRoute />}>
                <Route element={<Layout />}>
                  <Route index element={<Navigate to="/search" replace />} />
                  <Route path="search" element={<SearchPage />} />
                  <Route path="documents/:id" element={<DocumentPage />} />
                  <Route path="dashboard" element={<DashboardPage />} />
                </Route>
              </Route>
              <Route path="*" element={<Navigate to="/search" replace />} />
            </Routes>
          </LiveProvider>
        </AuthProvider>
      </BrowserRouter>
    </ToastProvider>
  </React.StrictMode>
);
