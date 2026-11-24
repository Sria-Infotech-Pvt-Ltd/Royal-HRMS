"use client";

import { useState, type FormEvent, type KeyboardEvent } from "react";
import { useT } from "@/hooks/useI18n";
import { searchAddress, type GeocodeResult } from "@/lib/geocode";

const MIN_QUERY_LENGTH = 4;

interface WfhAddressSearchProps {
  inputClassName: string;
  onPick: (result: GeocodeResult) => void;
}

/** Address lookup for a WFH location. Searches only when the Search button (or Enter) is pressed, never while typing. */
export default function WfhAddressSearch({ inputClassName, onPick }: WfhAddressSearchProps) {
  const t = useT();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<GeocodeResult[] | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [pickedIndex, setPickedIndex] = useState<number | null>(null);

  async function runSearch() {
    if (query.trim().length < MIN_QUERY_LENGTH) {
      setErrorMessage(t("Type at least the street, area and city."));
      return;
    }
    setErrorMessage("");
    setPickedIndex(null);
    setIsSearching(true);
    try {
      setResults(await searchAddress(query));
    } catch (caught: unknown) {
      setResults(null);
      setErrorMessage(caught instanceof Error ? caught.message : t("The address search failed. Please try again."));
    } finally {
      setIsSearching(false);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") return;
    event.preventDefault();
    void runSearch();
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void runSearch();
  }

  function pick(result: GeocodeResult, index: number) {
    setPickedIndex(index);
    onPick(result);
  }

  return (
    <form onSubmit={handleSubmit} className="mt-3">
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={query}
          onChange={event => setQuery(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t("House / street, area, city, pincode")}
          className={inputClassName}
          suppressHydrationWarning
        />
        <button
          type="submit"
          disabled={isSearching}
          suppressHydrationWarning
          className="px-4 py-2.5 rounded-xl text-sm font-semibold text-white disabled:opacity-60 whitespace-nowrap"
          style={{ background: "var(--primary)" }}
        >
          {isSearching ? t("Searching…") : t("Search")}
        </button>
      </div>

      {errorMessage && (
        <p role="alert" className="text-xs text-red-500 mt-2 flex items-center gap-1">
          <i className="ti ti-alert-circle text-xs" /> {errorMessage}
        </p>
      )}

      {results !== null && results.length === 0 && !errorMessage && (
        <p className="text-xs mt-2" style={{ color: "var(--on-variant)" }}>{t("No match found. Try adding the area, city or pincode.")}</p>
      )}

      {results !== null && results.length > 0 && (
        <div role="listbox" aria-label={t("Address matches")} className="flex flex-col gap-1.5 mt-3">
          {results.map((result, index) => {
            const isPicked = pickedIndex === index;
            return (
              <button
                key={`${result.latitude},${result.longitude},${index}`}
                type="button"
                role="option"
                aria-selected={isPicked}
                onClick={() => pick(result, index)}
                suppressHydrationWarning
                className="text-left px-3 py-2 rounded-lg text-sm border transition-colors"
                style={isPicked
                  ? { borderColor: "var(--success)", background: "var(--success-c)", color: "var(--success)" }
                  : { borderColor: "var(--outline-v)", background: "var(--bg-low)", color: "var(--on-bg)" }}
              >
                {result.label}
              </button>
            );
          })}
        </div>
      )}
    </form>
  );
}
