import React from "react";

function Results({ results, filters }) {
  return (
    <div>
      <h4>Filters Applied:</h4>
      <pre>{JSON.stringify(filters, null, 2)}</pre>
      <h4>Results:</h4>
      {results && results.length > 0 ? (
        <ul>
          {results.map(bond => (
            <li key={bond.id}>
              <b>{bond.bond_name}</b> | Issuer: {bond.issuer} | Currency: {bond.currency} | Return: {bond.return} | Duration: {bond.duration} | Status: {bond.status} | Segment: {bond.segment} | Industry: {bond.industry} | Country: {bond.country} | Maturity: {bond.maturity_date} | Coupon: {bond.coupon_rate}% | Credit: {bond.credit_rating} | Callable: {bond.callable ? "Yes" : "No"} | Puttable: {bond.puttable ? "Yes" : "No"} | Seniority: {bond.seniority} | Secured: {bond.secured ? "Yes" : "No"} | Tax: {bond.tax_status} | Min Investment: {bond.min_investment} | Frequency: {bond.frequency} | Exchange: {bond.listing_exchange} | Type: {bond.type} | Convertible: {bond.convertible ? "Yes" : "No"} | Perpetual: {bond.perpetual ? "Yes" : "No"} | Green: {bond.green_bond ? "Yes" : "No"} | Sinking Fund: {bond.sinking_fund ? "Yes" : "No"}
            </li>
          ))}
        </ul>
      ) : (
        <div>No results found.</div>
      )}
    </div>
  );
}

export default Results;
