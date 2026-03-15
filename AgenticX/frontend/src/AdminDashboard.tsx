import { useEffect, useState } from "react";

const API_BASE_URL = "http://127.0.0.1:8000";

export default function AdminDashboard() {

  const [orders, setOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const loadOrders = async () => {

    try {

      const res = await fetch(`${API_BASE_URL}/orders`);
      const data = await res.json();

      setOrders(data);

    } catch {

      console.log("Failed to load orders");

    }

    setLoading(false);

  };

  useEffect(() => {

    loadOrders();

    const interval = setInterval(loadOrders, 3000);

    return () => clearInterval(interval);

  }, []);

  // -----------------------------
  // Approve Order
  // -----------------------------

  const approve = async (flowId: string) => {

    try {

      await fetch(`${API_BASE_URL}/orders/${flowId}/human-approval`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          decision: "approve"
        })
      });

      loadOrders(); // refresh immediately

    } catch {

      alert("Failed to approve order");

    }

  };

  // -----------------------------
  // Reject Order
  // -----------------------------

  const reject = async (flowId: string) => {

    try {

      await fetch(`${API_BASE_URL}/orders/${flowId}/human-approval`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          decision: "reject"
        })
      });

      loadOrders(); // refresh immediately

    } catch {

      alert("Failed to reject order");

    }

  };

  return (

    <div style={{ padding: 40 }}>

      <h1>Admin Dashboard</h1>

      {loading && <p>Loading orders...</p>}

      {orders.length === 0 && !loading && (
        <p>No active orders</p>
      )}

      {orders.map((order: any) => (

        <div
          key={order.flow_id}
          style={{
            border: "1px solid gray",
            padding: 20,
            marginBottom: 20,
            borderRadius: 10
          }}
        >

          <h3>Order ID</h3>
          <p>{order.flow_id}</p>

          <p>
            <b>Status:</b>{" "}
            <span style={{
              color:
                order.status === "waiting_for_human_approval"
                  ? "orange"
                  : order.status === "payment_pending"
                  ? "blue"
                  : order.status === "payment_confirmed"
                  ? "green"
                  : "red"
            }}>
              {order.status}
            </span>
          </p>

          {order.supplier && (

            <div>

              <h4>AI Supplier Decision</h4>

              <p><b>Supplier:</b> {order.supplier.name}</p>
              <p><b>Price:</b> ${order.supplier.price}</p>
              <p><b>Shipping:</b> ${order.supplier.shipping}</p>

            </div>

          )}

          {order.status === "waiting_for_human_approval" && (

            <div style={{ marginTop: 10 }}>

              <button
                onClick={() => approve(order.flow_id)}
                style={{
                  padding: "8px 16px",
                  background: "green",
                  color: "white",
                  border: "none",
                  borderRadius: 5,
                  cursor: "pointer"
                }}
              >
                Approve
              </button>

              <button
                onClick={() => reject(order.flow_id)}
                style={{
                  marginLeft: 10,
                  padding: "8px 16px",
                  background: "red",
                  color: "white",
                  border: "none",
                  borderRadius: 5,
                  cursor: "pointer"
                }}
              >
                Reject
              </button>

            </div>

          )}

        </div>

      ))}

    </div>

  );

}

