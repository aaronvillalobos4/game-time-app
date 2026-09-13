import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { isBookingUrl } from "../lib/booking-links";

const components: Components = {
  a: ({ children, href, title }) => isBookingUrl(href) ? (
    <a href={href} title={title} target="_blank" rel="sponsored noopener noreferrer">
      {children}
    </a>
  ) : <span>{children}</span>,
  img: ({ alt }) => <span>{alt}</span>,
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
