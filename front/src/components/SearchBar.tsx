import { useState } from "react";
import { HOME } from "../content/copy";
import styles from "./SearchBar.module.css";

/**
 * A persistent label, not a placeholder-only field: placeholders vanish on
 * input, which docs/13 §10 rules out for the primary control.
 */
export function SearchBar({
  defaultValue = "",
  onSubmit,
}: {
  defaultValue?: string;
  onSubmit: (query: string) => void;
}) {
  const [value, setValue] = useState(defaultValue);

  return (
    <form
      className={styles.form}
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(value.trim());
      }}
      role="search"
    >
      <label className={styles.label} htmlFor="search-input">
        {HOME.searchLabel}
      </label>
      <p className={styles.hint} id="search-hint">
        {HOME.searchHint}
      </p>
      <div className={styles.row}>
        <input
          id="search-input"
          className={styles.input}
          type="search"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder={HOME.searchPlaceholder}
          aria-describedby="search-hint"
        />
        <button type="submit" className={styles.submit}>
          {HOME.submit}
        </button>
      </div>
    </form>
  );
}
