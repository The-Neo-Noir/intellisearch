import React, { useState } from "react";

function Feedback({ onSubmit }) {
  const [feedback, setFeedback] = useState("");

  const handleThumb = (type) => {
    setFeedback(type === "up" ? "👍" : "👎");
    onSubmit(type === "up" ? "helpful" : "not helpful");
  };

  return (
    <div>
      <h4>How accurate were the search results?</h4>
      <div>
        <button onClick={() => handleThumb("up")} title="Helpful">
          👍
        </button>
        <button onClick={() => handleThumb("down")} title="Not Helpful">
          👎
        </button>
      </div>
      <div style={{ marginTop: "8px" }}>
        <small>
          Click <b>👍</b> if the results were helpful, or <b>👎</b> if not helpful.
          <br />
          Optionally, you can type specific feedback below:
        </small>
      </div>
      <input
        type="text"
        placeholder="Additional feedback (optional)"
        value={feedback}
        onChange={(e) => setFeedback(e.target.value)}
        style={{ width: "300px", marginTop: "8px" }}
      />
      <button
        onClick={() => onSubmit(feedback)}
        style={{ marginLeft: "8px" }}
      >
        Submit Feedback
      </button>
    </div>
  );
}

export default Feedback;
