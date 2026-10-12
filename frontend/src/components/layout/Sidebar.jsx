import SidebarContent from "./SidebarContent";
import SidebarFooter from "./SidebarFooter";
import SidebarHeader from "./SidebarHeader";

// Fixed-width tree panel. Never collapses to an icon rail: the "airy" design
// keeps labels and counts visible at all times instead of icon-only mode.
function Sidebar() {
  return (
    <aside className="hidden w-[300px] flex-col border-r border-border bg-card md:flex">
      <SidebarHeader />
      <SidebarContent />
      <SidebarFooter />
    </aside>
  );
}

export default Sidebar;
