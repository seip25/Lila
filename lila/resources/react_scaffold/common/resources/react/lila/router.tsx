// React Router helpers for SPAs served by router.spa("/app", meta={...}).
//
//   const router = createRouter([
//     { element: <AppLayout />, children: [
//       { index: true, element: <Home /> },
//       { path: "users/:id", lazy: page(() => import("./pages/spa/User")) },
//     ]},
//   ]);
//   createLilaSpa(() => <RouterProvider router={router} />);
import type { ComponentType } from "react";
import {
  createBrowserRouter, createHashRouter, createMemoryRouter, useLocation, type RouteObject,
} from "react-router";
import { readPage, useLilaHead } from "./index";

export type RouterMode = "browser" | "hash" | "memory";

export interface CreateRouterOptions {
  /** Default: the router.spa() mount ("/app"); "/" for hash/memory. */
  basename?: string;
  /** browser (default), hash (file:// / static builds) or memory (tests). */
  mode?: RouterMode;
  initialEntries?: string[];
}

export function createRouter(routes: RouteObject[], options: CreateRouterOptions = {}) {
  const mode: RouterMode = options.mode || (window.location.protocol === "file:" ? "hash" : "browser");
  if (mode === "memory") return createMemoryRouter(routes, { initialEntries: options.initialEntries || ["/"] });
  if (mode === "hash") return createHashRouter(routes);
  const mount = options.basename ?? readPage().spa?.mount ?? "/";
  return createBrowserRouter(routes, mount && mount !== "/" ? { basename: mount } : undefined);
}

/** `lazy` for a page module with a default export: { path, lazy: page(() => import("./X")) } */
export function page(loader: () => Promise<{ default: ComponentType<any> }>) {
  return async () => ({ Component: (await loader()).default });
}

/** Refreshes <title>/meta/JSON-LD from the server meta tree on every navigation. */
export function LilaHead() {
  useLilaHead(useLocation().pathname);
  return null;
}
