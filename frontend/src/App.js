import React, { useState } from "react";
import SearchBox from "./SearchBox";
import Results from "./Results";
import Feedback from "./Feedback";

function App() {
  const [results, setResults] = useState([]);
  const [filters, setFilters] = useState({});
  const [searchId, setSearchId] = useState(null);

  const handleSearch = async (query) => {
    const res = await fetch("http://localhost:8000/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, user_id: "frontier1" }),
    });
    if (!res.ok) throw new Error("Backend error");
    const data = await res.json();
    setResults(data.results);
    setFilters(data.filters);
    setSearchId(data.search_id);
  };

  const handleFeedback = async (feedback) => {
    await fetch("http://localhost:8000/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ search_id: searchId, feedback }),
    });
    alert("Feedback submitted!");
  };

  return (
    <div>
      <h2>Smart Bond Search (POC)</h2>
      <SearchBox onSearch={handleSearch} />
      <Results results={results} filters={filters} />
      {searchId && <Feedback onSubmit={handleFeedback} />}
    </div>
  );
}

export default App;
