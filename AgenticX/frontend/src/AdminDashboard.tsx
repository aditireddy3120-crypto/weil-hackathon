import { useEffect, useState } from "react";

const API_BASE_URL = "http://127.0.0.1:8000";

export default function AdminDashboard() {

  const [orders, setOrders] = useState<any[]>([]);

  const loadOrders = async () => {

    const res = await fetch(`${API_BASE_URL}/orders`);
    const data = await res.json();

    setOrders(data);

  };

  useEffect(() => {

    loadOrders();

    const interval = setInterval(loadOrders, 3000);

    return () => clearInterval(interval);

  }, []);

  const approve = async (flowId: string) => {

    await fetch(`${API_BASE_URL}/orders/${flowId}/human-approval`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        decision: "approved"
      })
    });

  };

  const reject = async (flowId: string) => {

    await fetch(`${API_BASE_URL}/orders/${flowId}/human-approval`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        decision: "rejected"
      })
    });

  };

  return (

    <div>

      <h1>Admin Dashboard</h1>

      {orders.map(order => (

        <div
          key={order.flow_id}
          style={{
            border: "1px solid gray",
            padding: 20,
            marginBottom: 20
          }}
        >

          <h3>Order ID: {order.flow_id}</h3>

          <p>Status: {order.status}</p>

          {order.supplier && (
            <div>

              <h4>AI Supplier Decision</h4>

              <p>Supplier: {order.supplier.name}</p>
              <p>Price: ${order.supplier.price}</p>
              <p>Shipping: ${order.supplier.shipping}</p>

            </div>
          )}

          {order.status === "waiting_for_human_approval" && (
            <div style={{ marginTop: 10 }}>

              <button onClick={() => approve(order.flow_id)}>
                Approve
              </button>

              <button
                onClick={() => reject(order.flow_id)}
                style={{ marginLeft: 10 }}
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