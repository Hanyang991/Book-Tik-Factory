import { useEffect, useState } from "react";
import Dashboard from "./components/Dashboard";
import MobileLanding from "./components/MobileLanding";
import { Toaster } from "./components/ui/sonner";

export default function App() {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkViewport = () => {
      // 임시로 768px로 낮춤 (테스트용)
      setIsMobile(window.innerWidth < 768);
    };

    checkViewport();
    window.addEventListener("resize", checkViewport);
    return () => window.removeEventListener("resize", checkViewport);
  }, []);

  return (
    <div className="size-full">
      {isMobile ? <MobileLanding /> : <Dashboard />}
      <Toaster
        theme="dark"
        position="top-right"
        toastOptions={{
          style: {
            background: '#2c1810',
            color: '#f5f0e8',
            border: '1px solid rgba(212, 162, 76, 0.20)',
          },
        }}
      />
    </div>
  );
}
