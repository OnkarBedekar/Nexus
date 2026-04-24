import React from "react";
import ReactDOM from "react-dom/client";
import { Provider as UrqlProvider } from "urql";
import { graphqlClient } from "./api/graphqlClient";
import { App } from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <UrqlProvider value={graphqlClient}>
      <App />
    </UrqlProvider>
  </React.StrictMode>,
);
