import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

const components: Components = {
  a: ({ children, href, title }) => (
    <a href={href} title={title} target="_blank" rel="sponsored noopener noreferrer">
      {children}
    </a>
  ),
  table: ({ children }) => (
    <div className="trip-table-scroll" role="region" aria-label="Scrollable trip details table" tabIndex={0}>
      <table>{children}</table>
    </div>
  ),
  th: ({ children, style }) => <th scope="col" style={style}>{children}</th>,
};

/** One Markdown presentation for conversational answers and generated itineraries. */
export default function TripMarkdown({ children }: { children: string }) {
  return (
    <div className="trip-markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components} skipHtml>
        {children}
      </ReactMarkdown>
    </div>
  );
}
