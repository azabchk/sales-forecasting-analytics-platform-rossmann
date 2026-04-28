import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import LoadingBlock from "./LoadingBlock";

type Props = { children: React.ReactNode };

export default function ProtectedRoute({ children }: Props) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div style={{ padding: "48px 32px" }}>
        <LoadingBlock lines={4} />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}
