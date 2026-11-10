
import { useCallback, useEffect, useRef, useState } from "react";

export function usePolling(
  fetcher,
  {
    enabled = true,
    intervalMs = 1000,
    stopWhen = () => false,
  } = {}
) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [isPolling, setIsPolling] = useState(false);

  const fetcherRef = useRef(fetcher);
  const stopWhenRef = useRef(stopWhen);

  useEffect(() => {
    fetcherRef.current = fetcher;
    stopWhenRef.current = stopWhen;
  }, [fetcher, stopWhen]);

  const [refreshVersion, setRefreshVersion] = useState(0);

  const refresh = useCallback(() => {
    setRefreshVersion((version) => version + 1);
  }, []);

  useEffect(() => {
    if (!enabled) {
      setIsPolling(false);
      return;
    }

    let active = true;
    let timeoutId;
    let controller;

    const poll = async () => {
      if (!active) return;

      controller = new AbortController();
      setIsPolling(true);

      try {
        const result = await fetcherRef.current({
          signal: controller.signal,
        });

        if (!active) return;

        setData(result);
        setError(null);
        setLastUpdated(new Date());

        if (stopWhenRef.current(result)) {
          setIsPolling(false);
          return;
        }
      } catch (err) {
        if (!active || err.name === "AbortError") return;
        setError(err);
      } finally {
        if (active) setIsPolling(false);
      }

      if (active) {
        timeoutId = setTimeout(poll, intervalMs);
      }
    };

    // Fetch immediately, then wait intervalMs between completed requests.
    poll();

    return () => {
      active = false;
      clearTimeout(timeoutId);
      controller?.abort();
    };
  }, [enabled, intervalMs, refreshVersion]);

  return {
    data,
    error,
    lastUpdated,
    isPolling,
    refresh,
  };
}
