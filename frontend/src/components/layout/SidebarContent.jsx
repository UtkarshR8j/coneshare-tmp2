import React from "react";
import { Bot, File, Home, LayoutGrid, UploadCloud, Trash2 } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { cn } from "../../lib/utils";
import DataroomFolderTree from "./DataroomFolderTree";

export const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: Home },
  { href: "/documents", label: "Documents", icon: File },
  { href: "/datarooms", label: "Datarooms", icon: LayoutGrid },
  { href: "/file-requests", label: "File Requests", icon: UploadCloud },
  { href: "/automations", label: "Automations", icon: Bot },
  { href: "/trash", label: "Trash", icon: Trash2, hasDivider: true },
];

export function useNavItems() {
  const { t } = useTranslation();
  return [
    { href: "/dashboard", label: t('nav.dashboard'), icon: Home },
    { href: "/documents", label: t('nav.documents'), icon: File },
    { href: "/datarooms", label: t('nav.datarooms'), icon: LayoutGrid },
    { href: "/file-requests", label: t('nav.fileRequests'), icon: UploadCloud },
    { href: "/automations", label: t('nav.automations'), icon: Bot },
    { href: "/trash", label: t('nav.trash'), icon: Trash2, hasDivider: true },
  ];
}

function SidebarContent() {
  const { pathname } = useLocation();
  const navItems = useNavItems();

  return (
    <nav className="mt-4 flex flex-col gap-1 p-2">
      {navItems.map((item) => (
        <React.Fragment key={item.href}>
          {item.hasDivider && (
            <hr className="my-1.5 border-t border-border" />
          )}
          <Link
            to={item.href}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:text-foreground",
              (item.href === "/" ? pathname === item.href : pathname.startsWith(item.href)) &&
                "bg-secondary text-foreground"
            )}
          >
            <item.icon className="h-[18px] w-[18px]" />
            <span>{item.label}</span>
          </Link>
        </React.Fragment>
      ))}
      {/* Folder tree for the dataroom currently being viewed. Renders nothing outside
          /datarooms/:id, since a dataroom is 1:1 with its recipient. */}
      <DataroomFolderTree />
    </nav>
  );
}
export default SidebarContent;
