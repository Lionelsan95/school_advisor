import { useNavigate } from "react-router-dom";
import { SearchBar } from "../components/SearchBar";
import { HOME } from "../content/copy";
import styles from "./HomePage.module.css";

export function HomePage() {
  const navigate = useNavigate();

  return (
    <main className={styles.page}>
      <h1 className={styles.title}>{HOME.title}</h1>
      <p className={styles.intro}>{HOME.intro}</p>

      <SearchBar
        onSubmit={(query) =>
          navigate(query ? `/recherche?q=${encodeURIComponent(query)}` : "/recherche")
        }
      />

      <section aria-labelledby="commitments">
        <h2 id="commitments" className={styles.sectionTitle}>
          {HOME.commitmentsTitle}
        </h2>
        <ul className={styles.commitments}>
          {HOME.commitments.map((item) => (
            <li key={item.title} className={styles.commitment}>
              <h3 className={styles.commitmentTitle}>{item.title}</h3>
              <p className={styles.commitmentBody}>{item.body}</p>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
