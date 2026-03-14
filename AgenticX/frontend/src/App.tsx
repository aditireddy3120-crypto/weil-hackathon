import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import CustomerStore from "./CustomerStore";
import AdminDashboard from "./AdminDashboard";

export default function App() {
  return (
    <BrowserRouter>

      <div
        style={{
          padding: 20,
          background: "#020617",
          minHeight: "100vh",
          color: "white",
          fontFamily: "sans-serif"
        }}
      >

        {/* Navigation */}
        <nav
          style={{
            marginBottom: 30,
            display: "flex",
            gap: 20,
            fontSize: 18
          }}
        >
          <Link
            to="/"
            style={{
              color: "#38bdf8",
              textDecoration: "none",
              fontWeight: "bold"
            }}
          >
            🛒 Customer Store
          </Link>

          <Link
            to="/admin"
            style={{
              color: "#f472b6",
              textDecoration: "none",
              fontWeight: "bold"
            }}
          >
            ⚙ Admin Dashboard
          </Link>
        </nav>

        {/* Pages */}
        <Routes>
          <Route path="/" element={<CustomerStore />} />
          <Route path="/admin" element={<AdminDashboard />} />
        </Routes>

      </div>

    </BrowserRouter>
  );
}