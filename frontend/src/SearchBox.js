import React, { useState, useEffect, useRef } from "react";

function getNextWordSuggestions(query, suggestionPhrases) {
  // Suggest phrases that start with the last word/phrase in the query
  const lastWord = query.split(" ").pop().toLowerCase();
  return suggestionPhrases
    .filter(phrase => phrase.toLowerCase().startsWith(lastWord) && phrase.toLowerCase() !== lastWord)
    .slice(0, 5);
}

function getPhraseSuggestions(query, suggestionPhrases) {
  // Suggest phrases that are not already in the query
  return suggestionPhrases
    .filter(phrase => !query.toLowerCase().includes(phrase.toLowerCase()))
    .slice(0, 5);
}

function SearchBox({ onSearch, userId = "frontier1" }) {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [error, setError] = useState(null);
  const [allSuggestionPhrases, setAllSuggestionPhrases] = useState([]);
  const suggestionBoxRef = useRef();

  useEffect(() => {
    // Fetch frontier profile for autocomplete suggestions
    fetch(`http://localhost:8000/frontier-profile/${userId}`)
      .then(res => res.json())
      .then(profile => {
        if (!profile) return;
        let sugg = [];
        // Singapore-specific values for frontier1, India-specific for frontier2, etc.
        if (profile.preferred_currency) sugg.push(profile.preferred_currency);
        if (profile.location) sugg.push(profile.location);
        // Add customer-specific preferences
        if (profile.customer_profiles) {
          profile.customer_profiles.forEach(cust => {
            if (cust.preferences) {
              Object.entries(cust.preferences).forEach(([k, v]) => {
                if (typeof v === "string") sugg.push(v);
                if (Array.isArray(v)) sugg = sugg.concat(v);
              });
            }
          });
        }
        // Add common bond search keywords
        sugg = sugg.concat([
          "bond", "bonds", "high yield", "high rating", "low rating", "high risk", "low risk",
          "callable", "puttable", "green bond", "tax-free", "fixed", "floating", "annual", "semi-annual", "quarterly"
        ]);
        setAllSuggestionPhrases([...new Set(sugg)]);
      });
  }, [userId]);

  useEffect(() => {
    if (!query) {
      setSuggestions([]);
      return;
    }
    // Suggest next word/phrase based on current query
    const nextWordSuggestions = getNextWordSuggestions(query, allSuggestionPhrases);
    // Also suggest phrases not already in the query
    const phraseSuggestions = getPhraseSuggestions(query, allSuggestionPhrases);
    setSuggestions([...nextWordSuggestions, ...phraseSuggestions]);
  }, [query, allSuggestionPhrases]);

  const handleSuggestionClick = (sugg) => {
    // Add the suggestion as the next word/phrase
    let words = query.trim().split(" ");
    words.pop();
    const newQuery = (words.join(" ") + " " + sugg).trim();
    setQuery(newQuery + " ");
  };

  const handleSearchClick = async () => {
    setError(null);
    try {
      await onSearch(query);
    } catch (err) {
      setError("Failed to fetch results. Please check your backend server.");
    }
  };

  // Close suggestions on outside click
  useEffect(() => {
    function handleClickOutside(event) {
      if (suggestionBoxRef.current && !suggestionBoxRef.current.contains(event.target)) {
        setSuggestions([]);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div style={{ position: "relative" }}>
      <input
        type="text"
        placeholder="Type your bond search (e.g. HSBC SGD high return)..."
        value={query}
        onChange={e => setQuery(e.target.value)}
        style={{ width: "400px" }}
        autoComplete="off"
      />
      <button onClick={handleSearchClick}>Search</button>
      {error && <div style={{ color: "red" }}>{error}</div>}
      {suggestions.length > 0 && (
        <div
          ref={suggestionBoxRef}
          style={{
            border: "1px solid #ccc",
            background: "#fff",
            position: "absolute",
            zIndex: 10,
            width: "400px",
            maxHeight: "180px",
            overflowY: "auto"
          }}
        >
          {suggestions.map((sugg, idx) => (
            <div
              key={idx}
              style={{ padding: "4px", cursor: "pointer" }}
              onClick={() => handleSuggestionClick(sugg)}
            >
              {sugg}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default SearchBox;
