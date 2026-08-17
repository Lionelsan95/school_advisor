import { Link, Route, Routes } from "react-router-dom";
import { ComparisonPage } from "./pages/ComparisonPage";
import { FactSheetPage } from "./pages/FactSheetPage";
import { GlossaryPage } from "./pages/GlossaryPage";
import { HistoryPage } from "./pages/HistoryPage";
import { HomePage } from "./pages/HomePage";
import { SearchResultsPage } from "./pages/SearchResultsPage";
import { NAV, SITE } from "./content/copy";
import styles from "./App.module.css";

export default function App() {
  return (
    <>
      <a className={styles.skip} href="#main">
        {NAV.skipToContent}
      </a>
      <header className={styles.header}>
        <Link to="/" className={styles.brand}>
          {SITE.name}
        </Link>
        <nav aria-label="Navigation principale">
          <Link to="/recherche">{NAV.search}</Link>{" "}
          <Link to="/glossaire">{NAV.glossary}</Link>
        </nav>
      </header>

      <div id="main">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/recherche" element={<SearchResultsPage />} />
          <Route path="/comparaison" element={<ComparisonPage />} />
          <Route path="/glossaire" element={<GlossaryPage />} />
          <Route path="/etablissements/:uai" element={<FactSheetPage />} />
          <Route
            path="/etablissements/:uai/historique"
            element={<HistoryPage />}
          />
        </Routes>
      </div>
    </>
  );
}
