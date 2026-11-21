// Client-side SPA served by router.spa("/app", meta={...}) in Python.
import "./app.css";
import { RouterProvider } from "react-router";
import { createLilaSpa } from "@lila";
import { AuthProvider } from "@lila/auth";
import { createRouter, page } from "@lila/router";
import AppLayout from "./spa/AppLayout";
import Home from "./spa/Home";

const router = createRouter([
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <Home /> },
      // Lazy routes: each page is its own chunk.
      { path: "users", lazy: page(() => import("./spa/Users")) },
      { path: "users/:id", lazy: page(() => import("./spa/User")) },
      { path: "account", lazy: page(() => import("./spa/Account")) },
      { path: "live", lazy: page(() => import("./spa/Live")) },
      { path: "billing", lazy: page(() => import("./spa/Billing")) },
      { path: "*", lazy: page(() => import("./spa/NotFound")) },
    ],
  },
]);

createLilaSpa(() => (
  <AuthProvider>
    <RouterProvider router={router} />
  </AuthProvider>
));
