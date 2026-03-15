import { useEffect, useState } from "react";

const API_BASE_URL = "http://127.0.0.1:8000";
const USD_TO_INR = 83;

export default function CustomerStore() {

  const [products, setProducts] = useState<any[]>([]);
  const [cart, setCart] = useState<any[]>([]);
  const [walletAddress, setWalletAddress] = useState<string | null>(null);

  const [flowId, setFlowId] = useState<string | null>(null);
  const [orderStatus, setOrderStatus] = useState<string>("not_started");

  const [paymentIntent, setPaymentIntent] = useState<any>(null);
  const [paying, setPaying] = useState(false);
  const [loadingProducts, setLoadingProducts] = useState(true);

  // -----------------------------
  // Restore order if page refreshed
  // -----------------------------

  useEffect(() => {

    const savedFlow = localStorage.getItem("flowId");

    if (savedFlow) {
      setFlowId(savedFlow);
    }

  }, []);

  // -----------------------------
  // Load products
  // -----------------------------

  useEffect(() => {

    const loadProducts = async () => {

      try {

        const res = await fetch(`${API_BASE_URL}/products`);
        const data = await res.json();

        setProducts(data);

      } catch {

        console.log("Failed to load products");

      }

      setLoadingProducts(false);

    };

    loadProducts();

  }, []);

  // -----------------------------
  // Poll order status
  // -----------------------------

  useEffect(() => {

    if (!flowId) return;

    const interval = setInterval(async () => {

      try {

        const res = await fetch(`${API_BASE_URL}/orders/${flowId}`);

        if (!res.ok) {

          // backend reset or order removed
          localStorage.removeItem("flowId");
          setFlowId(null);
          setOrderStatus("not_started");
          setPaymentIntent(null);
          return;

        }

        const data = await res.json();

        setOrderStatus(data.status);

        if (data.status !== "payment_pending") {
          setPaymentIntent(null);
        }

        // order rejected
        if (data.status === "rejected") {

          alert("Order rejected by admin");

          localStorage.removeItem("flowId");

          setFlowId(null);
          setCart([]);
          setPaymentIntent(null);
          setOrderStatus("not_started");

        }

        // order completed
        if (data.status === "payment_confirmed") {

          alert("Order completed successfully");

          localStorage.removeItem("flowId");

          setFlowId(null);
          setCart([]);
          setPaymentIntent(null);
          setOrderStatus("not_started");

        }

      } catch {

        console.log("Polling failed");

      }

    }, 2000);

    return () => clearInterval(interval);

  }, [flowId]);

  // -----------------------------
  // Fetch payment intent
  // -----------------------------

  useEffect(() => {

    if (!flowId) return;

    if (orderStatus === "payment_pending" && !paymentIntent) {

      fetch(`${API_BASE_URL}/orders/${flowId}/payment-intent`, {
        method: "POST"
      })
        .then(res => res.json())
        .then(setPaymentIntent)
        .catch(() => console.log("Payment intent error"));

    }

  }, [orderStatus, flowId]);

  // -----------------------------
  // Wallet connect
  // -----------------------------

  const connectWallet = () => {

    setWalletAddress("0xLOCAL_DEV_WALLET");

  };

  // -----------------------------
  // Add to cart
  // -----------------------------

  const addToCart = (product: any) => {

    const existing = cart.find(c => c.sku === product.sku);

    if (existing) {

      setCart(
        cart.map(c =>
          c.sku === product.sku
            ? { ...c, quantity: c.quantity + 1 }
            : c
        )
      );

    } else {

      setCart([...cart, { sku: product.sku, quantity: 1 }]);

    }

  };

  // -----------------------------
  // Create order
  // -----------------------------

  const createOrder = async () => {

    if (!walletAddress) {
      alert("Connect wallet first");
      return;
    }

    // allow new order if previous finished
    if (flowId && orderStatus !== "rejected" && orderStatus !== "payment_confirmed") {
      alert("Order already in progress");
      return;
    }

    try {

      const res = await fetch(`${API_BASE_URL}/orders`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          cart,
          customer_wallet: walletAddress
        })
      });

      const data = await res.json();

      setFlowId(data.flow_id);
      localStorage.setItem("flowId", data.flow_id);

      setOrderStatus(data.status);

      alert("Order created!");

    } catch {

      alert("Failed to create order");

    }

  };

  // -----------------------------
  // Pay with WUSD
  // -----------------------------

  const payWithWusd = async () => {

    if (!flowId || orderStatus !== "payment_pending") {
      alert("Payment not allowed");
      return;
    }

    if (!paymentIntent) {
      alert("Payment intent missing");
      return;
    }

    setPaying(true);

    const txHash = "0xMOCK_TX_" + Date.now();

    try {

      const res = await fetch(`${API_BASE_URL}/orders/${flowId}/payment-confirmed`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          tx_hash: txHash,
          amount_wusd: paymentIntent.amount_wusd
        })
      });

      if (!res.ok) throw new Error();

      alert("Payment successful!");

      localStorage.removeItem("flowId");

      setCart([]);
      setFlowId(null);
      setPaymentIntent(null);
      setOrderStatus("not_started");

    } catch {

      alert("Payment failed");

    }

    setPaying(false);

  };

  return (
    <div>

      <h1>Customer Store</h1>

      <button onClick={connectWallet}>
        {walletAddress ? "Wallet Connected" : "Connect Wallet"}
      </button>

      <h2>Products</h2>

      {loadingProducts && <p>Loading products...</p>}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 20
        }}
      >

        {products.map((p) => (

          <div
            key={p.sku}
            style={{
              border: "1px solid gray",
              padding: 15,
              borderRadius: 10,
              textAlign: "center"
            }}
          >

            {p.image && (
              <img
                src={p.image}
                alt={p.name}
                style={{
                  width: 120,
                  height: 120,
                  objectFit: "contain",
                  marginBottom: 10
                }}
              />
            )}

            <h3>{p.name}</h3>

            <p>₹ {(p.price * USD_TO_INR).toFixed(0)}</p>

            <button onClick={() => addToCart(p)}>
              Add to Cart
            </button>

          </div>

        ))}

      </div>

      <h2>Cart</h2>

      {cart.length === 0 && <p>Cart empty</p>}

      {cart.map((c, i) => (
        <p key={i}>
          {c.sku} x {c.quantity}
        </p>
      ))}

      <button onClick={createOrder} disabled={cart.length === 0}>
        Create Order
      </button>

      {flowId && (
        <p style={{ marginTop: 10 }}>
          Order Status: {orderStatus}
        </p>
      )}

      {orderStatus === "waiting_for_human_approval" && (
        <p style={{ color: "orange" }}>
          Waiting for admin approval...
        </p>
      )}

      {orderStatus === "payment_pending" && paymentIntent && (
        <div style={{ marginTop: 20 }}>

          <h3>Payment</h3>

          <button onClick={payWithWusd} disabled={paying}>
            {paying ? "Processing..." : "Pay with WUSD"}
          </button>

        </div>
      )}

    </div>
  );
}

