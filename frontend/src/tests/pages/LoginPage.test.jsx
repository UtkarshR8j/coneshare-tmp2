import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import LoginPage from "../../pages/LoginPage";
import OidcCallbackPage from "../../pages/OidcCallbackPage";
import { authService } from "../../services/authService";
import "../../i18n";

// Mock the mutable parts of authService, but keep the real storeTokenFragment
// so the OIDC callback tests exercise the actual fragment -> localStorage path.
vi.mock("../../services/authService", async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    login: vi.fn(),
    getPublicSettings: vi.fn(),
    authService: {
      ...actual.authService,
      login: vi.fn(),
      getPublicSettings: vi.fn(),
    },
  };
});

// Mock useNavigate from react-router
const mockedNavigate = vi.fn();
vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router");
  return {
    ...actual,
    useNavigate: () => mockedNavigate,
  };
});

describe("LoginPage", () => {
  beforeEach(() => {
    // Reset mocks before each test
    vi.resetAllMocks();
    localStorage.clear();
    window.location.hash = "";
    authService.getPublicSettings.mockResolvedValue({ enable_public_signup: false });
  });

  const renderComponent = () => {
    return render(
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<div>Homepage</div>} />
        </Routes>
      </MemoryRouter>
    );
  };

  const renderCallback = (hash) => {
    window.location.hash = hash;
    return render(
      <MemoryRouter initialEntries={["/auth/callback"]}>
        <Routes>
          <Route path="/auth/callback" element={<OidcCallbackPage />} />
          <Route path="/dashboard" element={<div>Dashboard</div>} />
        </Routes>
      </MemoryRouter>
    );
  };

  it("renders the login form correctly", () => {
    renderComponent();
    expect(
      screen.getByRole("heading", { name: /Sign In/i })
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/Email address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sign In/i })).toBeInTheDocument();
  });

  it("calls authService.login and navigates to the dashboard on successful login", async () => {
    authService.login.mockResolvedValue({});
    renderComponent();

    fireEvent.change(screen.getByLabelText(/Email address/i), {
      target: { value: "test@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/Password/i), {
      target: { value: "password123" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Sign In/i }));

    await waitFor(() => {
      expect(authService.login).toHaveBeenCalledWith(
        "test@example.com",
        "password123"
      );
    });

    await waitFor(() => {
      expect(mockedNavigate).toHaveBeenCalledWith("/dashboard");
    });
  });

  it("displays an error message on failed login", async () => {
    authService.login.mockRejectedValue(new Error("Invalid credentials"));
    renderComponent();

    fireEvent.change(screen.getByLabelText(/Email address/i), {
      target: { value: "wrong@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/Password/i), {
      target: { value: "wrongpassword" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Sign In/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Invalid credentials. Please try again.")
      ).toBeInTheDocument();
    });

    expect(mockedNavigate).not.toHaveBeenCalled();
  });

  it("shows signup link when public signup is enabled", async () => {
    authService.getPublicSettings.mockResolvedValue({ enable_public_signup: true });
    renderComponent();

    await waitFor(() => {
      expect(screen.getByRole('link', { name: /sign up/i })).toBeInTheDocument();
    });
  });

  it("hides signup link when public signup is disabled", async () => {
    authService.getPublicSettings.mockResolvedValue({ enable_public_signup: false });
    renderComponent();

    await waitFor(() => {
      expect(screen.queryByRole('link', { name: /sign up/i })).not.toBeInTheDocument();
    });
  });

  it("disables the submit button while loading", async () => {
    // Create a promise that we can resolve later to simulate a long request
    let resolveLogin;
    const loginPromise = new Promise((resolve) => {
      resolveLogin = resolve;
    });
    authService.login.mockReturnValue(loginPromise);

    renderComponent();

    fireEvent.change(screen.getByLabelText(/Email address/i), {
      target: { value: "test@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/Password/i), {
      target: { value: "password123" },
    });

    const submitButton = screen.getByRole("button", { name: /Sign In/i });
    fireEvent.click(submitButton);

    // After clicking, button should be disabled and show "Signing In..."
    await waitFor(() => {
      expect(submitButton).toBeDisabled();
      expect(screen.getByText("Signing In...")).toBeInTheDocument();
    });

    // Resolve the promise to finish the login process
    resolveLogin({});

    // Wait for the UI to update after login completes
    await waitFor(() => {
      expect(submitButton).not.toBeDisabled();
    });
  });

  it("renders the split-brand layout with photo panel and support note", () => {
    renderComponent();

    const tagline = screen.getByText(
      /secure file sharing utility for internal stakeholders/i
    );
    const aside = tagline.closest("aside");
    expect(aside).not.toBeNull();

    const style = `${aside.getAttribute("style") || ""}${aside.style.backgroundImage || ""}`;
    expect(style).toContain("/brand/left-panel.jpg");

    const logo = within(aside).getByAltText(/logo/i);
    expect(logo.getAttribute("src")).toBe("/brand/longstraw-carbon-logo-white.png");
    expect(logo.getAttribute("class")).toContain("h-[72px]");

    expect(
      screen.getByText(/Please contact tech@longstraw\.in in case of any issues/i)
    ).toBeInTheDocument();
  });

  it("keeps the sign-in form working inside the split layout", () => {
    authService.login.mockResolvedValue({});
    renderComponent();

    expect(screen.getByRole("heading", { name: /Sign In/i })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Email address/i), {
      target: { value: "a@b.com" },
    });
    fireEvent.change(screen.getByLabelText(/Password/i), {
      target: { value: "pw" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Sign In/i }));

    return waitFor(() => {
      expect(authService.login).toHaveBeenCalledWith("a@b.com", "pw");
    });
  });

  it("offers Login with longstraw.earth above the email form", () => {
    renderComponent();

    const google = screen.getByRole("link", { name: /login with longstraw.earth/i });
    expect(google.getAttribute("href")).toBe("/api/v1/oidc/login/");
    expect(google.className).toContain("#00677f");

    // The Google entry point sits above the email/password form.
    const email = screen.getByLabelText(/Email address/i);
    const follows =
      google.compareDocumentPosition(email) & Node.DOCUMENT_POSITION_FOLLOWING;
    expect(follows).toBeTruthy();
    expect(
      screen.getByText(/or continue with email/i)
    ).toBeInTheDocument();
  });

  it("stores tokens from the OIDC callback fragment and routes to the dashboard", async () => {
    renderCallback("#access=access.jwt.value&refresh=refresh.jwt.value");

    await waitFor(() => {
      expect(localStorage.getItem("access_token")).toBe("access.jwt.value");
      expect(localStorage.getItem("refresh_token")).toBe("refresh.jwt.value");
    });
    expect(mockedNavigate).toHaveBeenCalledWith("/dashboard", { replace: true });
    expect(screen.queryByText(/sign-in failed/i)).not.toBeInTheDocument();
  });

  it("shows a clear error when the OIDC callback reports a failure", async () => {
    renderCallback("#error=state_mismatch");

    await waitFor(() => {
      expect(
        screen.getByText("Sign-in failed. Please try again.")
      ).toBeInTheDocument();
    });
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(mockedNavigate).not.toHaveBeenCalled();
  });

  it("shows the error state when the callback arrives without tokens", async () => {
    renderCallback("");

    await waitFor(() => {
      expect(
        screen.getByText("Sign-in failed. Please try again.")
      ).toBeInTheDocument();
    });
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(mockedNavigate).not.toHaveBeenCalled();
  });
});
