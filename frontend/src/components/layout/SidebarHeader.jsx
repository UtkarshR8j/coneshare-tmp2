import { Link } from "react-router-dom";
import { useBranding } from "../../contexts/BrandingProvider";

// No collapse toggle: the tree panel is fixed-width by design, so a
// chevron would be a control that does nothing.
function SidebarHeader() {
  const { brandName, brandLogoUrl, brandWebsiteUrl } = useBranding();

  const logoContent = (
    <>
      <img src={brandLogoUrl} alt={`${brandName} logo`} className="h-7 w-7 object-contain" />
      <span>{brandName}</span>
    </>
  );

  return (
    <div className="flex h-16 items-center border-b border-border px-5">
      {brandWebsiteUrl ? (
        <a
          href={brandWebsiteUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex flex-1 items-center gap-2 font-semibold"
          aria-label={`${brandName} Home`}
        >
          {logoContent}
        </a>
      ) : (
        <Link
          to="/dashboard"
          className="flex flex-1 items-center gap-2 font-semibold"
          aria-label={`${brandName} Home`}
        >
          {logoContent}
        </Link>
      )}
    </div>
  );
}
export default SidebarHeader;
