import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type AnchorHTMLAttributes,
  type MouseEvent,
  type ReactNode
} from "react";

interface LocationState {
  pathname: string;
  search: string;
}

interface RouterValue {
  location: LocationState;
  navigate: (to: string, options?: { replace?: boolean }) => void;
}

const RouterContext = createContext<RouterValue | null>(null);

function readLocation(): LocationState {
  return { pathname: window.location.pathname, search: window.location.search };
}

export function RouterProvider({ children }: { children: ReactNode }) {
  const [location, setLocation] = useState<LocationState>(readLocation);

  useEffect(() => {
    const onPopState = () => setLocation(readLocation());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = useCallback((to: string, options?: { replace?: boolean }) => {
    const destination = new URL(to, window.location.origin);
    if (destination.origin !== window.location.origin) {
      throw new Error("CROSS_ORIGIN_NAVIGATION_FORBIDDEN");
    }
    const next = `${destination.pathname}${destination.search}`;
    if (options?.replace) window.history.replaceState(null, "", next);
    else window.history.pushState(null, "", next);
    setLocation(readLocation());
  }, []);

  const value = useMemo(() => ({ location, navigate }), [location, navigate]);
  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
}

export function useRouter() {
  const value = useContext(RouterContext);
  if (!value) throw new Error("ROUTER_CONTEXT_MISSING");
  return value;
}

interface RouterLinkProps extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> {
  to: string;
}

export function RouterLink({ to, onClick, target, ...props }: RouterLinkProps) {
  const { navigate } = useRouter();
  const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event);
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.altKey ||
      event.ctrlKey ||
      event.shiftKey ||
      (target && target !== "_self")
    ) {
      return;
    }
    event.preventDefault();
    navigate(to);
  };
  return <a {...props} href={to} target={target} onClick={handleClick} />;
}
