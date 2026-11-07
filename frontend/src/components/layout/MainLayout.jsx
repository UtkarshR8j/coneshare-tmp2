import { Outlet } from "react-router-dom";
import Header from "./Header";
import Sidebar from "./Sidebar";
import { BreadcrumbProvider } from "./BreadcrumbProvider";
import { SidebarProvider } from "./SidebarProvider";
import { UserProvider } from "../../contexts/UserProvider";
import { UploadProgressIndicator } from "../documents/UploadProgressIndicator";
import { useLanguageSync } from "../../hooks/useLanguageSync";

function Layout() {
  useLanguageSync();
  // "Airy" layout: the tree panel is a fixed 300px column and never collapses
  // into an icon rail. Collapsing to icons hid the labels the whole design
  // depends on, so the toggle is intentionally not wired up here.
  // `.dark` is scoped HERE and deliberately NOT on <html>: the public share
  // viewer (/view/:slug) is a branded light surface with its own hardcoded
  // palette, and a global dark class bled into it and destroyed its contrast.
  return (
    <div className="grid h-screen w-full bg-background text-foreground md:grid-cols-[300px_1fr]">
      <Sidebar />
      <div className="grid grid-rows-[auto_1fr] overflow-hidden">
        <Header />
        <main className="overflow-auto p-5 md:p-8">
          <Outlet />
        </main>
      </div>
      <UploadProgressIndicator />
    </div>
  );
}

function MainLayout() {
  return (
    <SidebarProvider>
      <UserProvider>
        <BreadcrumbProvider>
          <Layout />
        </BreadcrumbProvider>
      </UserProvider>
    </SidebarProvider>
  );
}

export default MainLayout;
