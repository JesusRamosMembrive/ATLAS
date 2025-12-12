import {
    type PointerEvent as ReactPointerEvent,
    forwardRef,
    useCallback,
    useEffect,
    useImperativeHandle,
    useMemo,
    useRef,
    useState,
} from "react";
import type { UMLClass } from "../../api/types";
import { type UmlSvgHandle, type UmlViewState, UML_ZOOM_MAX, UML_ZOOM_MIN } from "./types";

interface ClassDetailsPanelProps {
    classInfo: UMLClass;
    onClose: () => void;
}

function ClassDetailsPanel({ classInfo, onClose }: ClassDetailsPanelProps): JSX.Element {
    const panelRef = useRef<HTMLElement>(null);

    // Auto-focus panel when opened for accessibility
    useEffect(() => {
        panelRef.current?.focus();
    }, []);

    return (
        <aside
            ref={panelRef}
            className="class-details-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="class-details-title"
            tabIndex={-1}
        >
            <header className="class-details-header">
                <h2 id="class-details-title">{classInfo.name}</h2>
                <button
                    type="button"
                    className="link-btn"
                    onClick={onClose}
                    aria-label="Close details panel"
                    title="Close (Esc)"
                >
                    ✕
                </button>
            </header>

            <div className="class-details-body">
                <section className="class-details-section">
                    <h3>Information</h3>
                    <dl>
                        <dt>Module</dt>
                        <dd>{classInfo.module}</dd>
                        <dt>File</dt>
                        <dd>{classInfo.file}</dd>
                        {classInfo.bases.length > 0 && (
                            <>
                                <dt>Inherits from</dt>
                                <dd>{classInfo.bases.join(", ")}</dd>
                            </>
                        )}
                    </dl>
                </section>

                {classInfo.attributes.length > 0 && (
                    <section className="class-details-section">
                        <h3>Attributes ({classInfo.attributes.length})</h3>
                        <ul className="class-members-list">
                            {classInfo.attributes.map((attr, idx) => (
                                <li key={idx}>
                                    <code className="member-name">{attr.name}</code>
                                    {attr.type && <span className="member-type">: {attr.type}</span>}
                                    {attr.optional && <span className="member-optional"> (optional)</span>}
                                </li>
                            ))}
                        </ul>
                    </section>
                )}

                {classInfo.methods.length > 0 && (
                    <section className="class-details-section">
                        <h3>Methods ({classInfo.methods.length})</h3>
                        <ul className="class-members-list">
                            {classInfo.methods.map((method, idx) => (
                                <li key={idx}>
                                    <code className="member-name">{method.name}</code>
                                    <code className="member-signature">
                                        ({method.parameters.join(", ")})
                                        {method.returns && ` → ${method.returns}`}
                                    </code>
                                </li>
                            ))}
                        </ul>
                    </section>
                )}

                {classInfo.associations.length > 0 && (
                    <section className="class-details-section">
                        <h3>Associations ({classInfo.associations.length})</h3>
                        <ul className="class-associations-list">
                            {classInfo.associations.map((assoc, idx) => (
                                <li key={idx}>
                                    <code>{assoc}</code>
                                </li>
                            ))}
                        </ul>
                    </section>
                )}
            </div>
        </aside>
    );
}

interface UmlSvgContainerProps {
    svg: string;
    onStateChange?: (state: UmlViewState) => void;
    onNodeClick?: (classId: string) => void;
    selectedNodeId?: string | null;
}

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const initialOffset = { x: 0, y: 0 };

export const UmlSvgContainer = forwardRef<UmlSvgHandle, UmlSvgContainerProps>(
    function UmlSvgContainer(
        { svg, onStateChange, onNodeClick, selectedNodeId },
        ref,
    ) {
        const containerRef = useRef<HTMLDivElement | null>(null);
        const [zoom, setZoomState] = useState(1);
        const [offset, setOffsetState] = useState(initialOffset);
        const [contentOrigin, setContentOrigin] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
        const panState = useRef<{
            pointerId: number;
            startX: number;
            startY: number;
            originX: number;
            originY: number;
        } | null>(null);
        const fitState = useRef<
            | {
                zoom: number;
                offset: { x: number; y: number };
                origin: { x: number; y: number };
            }
            | null
        >(null);
        const zoomRef = useRef(1);
        const [isPanning, setIsPanning] = useState(false);

        /**
         * Sanitize SVG content to prevent XSS attacks.
         * Removes script tags, event handlers, and dangerous attributes.
         */
        const sanitizeSvg = useCallback((svgContent: string): string => {
            // Remove script tags
            let sanitized = svgContent.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "");

            // Remove event handlers (onclick, onload, etc.)
            sanitized = sanitized.replace(/\s*on\w+\s*=\s*["'][^"']*["']/gi, "");
            sanitized = sanitized.replace(/\s*on\w+\s*=\s*[^\s>]*/gi, "");

            // Remove javascript: protocol in attributes
            sanitized = sanitized.replace(/javascript:/gi, "");

            // Remove data: URIs (except for safe SVG images)
            sanitized = sanitized.replace(/data:(?!image\/svg\+xml)[^"']*/gi, "");

            return sanitized;
        }, []);

        const content = useMemo(() => ({ __html: sanitizeSvg(svg) }), [svg, sanitizeSvg]);

        useEffect(() => {
            zoomRef.current = zoom;
        }, [zoom]);

        const applyZoom = useCallback(
            (targetZoom: number, anchor?: { x: number; y: number }) => {
                const container = containerRef.current;
                if (!container) {
                    return;
                }
                const rect = container.getBoundingClientRect();
                setZoomState((prevZoom) => {
                    const base = prevZoom === 0 ? 1 : prevZoom;
                    const clamped = clamp(targetZoom, UML_ZOOM_MIN, UML_ZOOM_MAX);
                    const scale = clamped / base;
                    setOffsetState((prevOffset) => {
                        const pivotX = anchor?.x ?? rect.width / 2;
                        const pivotY = anchor?.y ?? rect.height / 2;
                        const nextOffset = {
                            x: pivotX - (pivotX - prevOffset.x) * scale,
                            y: pivotY - (pivotY - prevOffset.y) * scale,
                        };
                        return nextOffset;
                    });
                    return clamped;
                });
            },
            [],
        );

        const updateFitState = useCallback(() => {
            const container = containerRef.current;
            const svgElement = container?.querySelector("svg");
            if (!container || !svgElement) {
                return;
            }

            const containerRect = container.getBoundingClientRect();
            if (containerRect.width === 0 || containerRect.height === 0) {
                return;
            }
            const view = svgElement.viewBox?.baseVal;
            const rawWidth =
                view?.width || parseSvgDimension(svgElement.getAttribute("width")) || 0;
            const rawHeight =
                view?.height || parseSvgDimension(svgElement.getAttribute("height")) || 0;
            let bbox: DOMRect | null = null;
            try {
                const candidate = svgElement.getBBox();
                if (Number.isFinite(candidate.x) && Number.isFinite(candidate.y)) {
                    bbox = candidate;
                }
            } catch {
                bbox = null;
            }
            const contentWidth = bbox?.width && bbox.width > 0 ? bbox.width : rawWidth;
            const contentHeight = bbox?.height && bbox.height > 0 ? bbox.height : rawHeight;
            if (!contentWidth || !contentHeight) {
                return;
            }
            const desiredZoom = 1;
            const fitZoom = clamp(desiredZoom, UML_ZOOM_MIN, UML_ZOOM_MAX);
            const scaledWidth = contentWidth * fitZoom;
            const scaledHeight = contentHeight * fitZoom;
            const offsetX = containerRect.width / 2 - scaledWidth / 2;
            const offsetY = containerRect.height / 2 - scaledHeight / 2;
            const origin = {
                x: bbox?.x ?? 0,
                y: bbox?.y ?? 0,
            };
            const next = {
                zoom: fitZoom,
                offset: {
                    x: Number.isFinite(offsetX) ? offsetX : initialOffset.x,
                    y: Number.isFinite(offsetY) ? offsetY : initialOffset.y,
                },
                origin,
            };
            fitState.current = next;
            zoomRef.current = next.zoom;
            setZoomState(next.zoom);
            setOffsetState(next.offset);
            setContentOrigin(origin);
            panState.current = null;
            setIsPanning(false);
            onStateChange?.({ zoom: next.zoom });
        }, [onStateChange]);

        useEffect(() => {
            const frame = requestAnimationFrame(updateFitState);
            return () => cancelAnimationFrame(frame);
        }, [svg, updateFitState]);

        // Handle node clicks and highlighting
        useEffect(() => {
            const container = containerRef.current;
            if (!container || !onNodeClick) {
                return;
            }

            const handleClick = (event: MouseEvent) => {
                // Find if we clicked on a node or its children
                let target = event.target as Element | null;
                let nodeElement: Element | null = null;

                // Walk up the DOM tree to find the .node element
                while (target && target !== container) {
                    if (target.classList?.contains("node")) {
                        nodeElement = target;
                        break;
                    }
                    target = target.parentElement;
                }

                if (nodeElement) {
                    // Extract class ID from the <title> element
                    const titleElement = nodeElement.querySelector("title");
                    if (titleElement) {
                        const classId = titleElement.textContent?.trim();
                        if (classId) {
                            onNodeClick(classId);
                        }
                    }
                }
            };

            container.addEventListener("click", handleClick);
            return () => container.removeEventListener("click", handleClick);
        }, [onNodeClick]);

        // Apply highlighting to selected node
        useEffect(() => {
            const container = containerRef.current;
            if (!container) {
                return;
            }

            // Remove previous highlights
            const previousHighlights = container.querySelectorAll(".node.highlighted");
            previousHighlights.forEach((node) => node.classList.remove("highlighted"));

            if (!selectedNodeId) {
                return;
            }

            // Find and highlight the selected node
            const nodes = container.querySelectorAll(".node");
            nodes.forEach((node) => {
                const title = node.querySelector("title");
                if (title?.textContent?.trim() === selectedNodeId) {
                    node.classList.add("highlighted");
                }
            });
        }, [selectedNodeId, svg]);

        useEffect(() => {
            onStateChange?.({ zoom });
        }, [zoom, onStateChange]);

        useEffect(() => {
            const container = containerRef.current;
            if (!container) {
                return;
            }
            const handler = (event: WheelEvent) => {
                if (!event.ctrlKey) {
                    event.preventDefault();
                }
                const delta = event.deltaY;
                const factor = delta < 0 ? 1.1 : 0.9;
                const rect = container.getBoundingClientRect();
                const anchor = {
                    x: event.clientX - rect.left,
                    y: event.clientY - rect.top,
                };
                applyZoom(zoomRef.current * factor, anchor);
            };
            container.addEventListener("wheel", handler, { passive: false });
            return () => container.removeEventListener("wheel", handler);
        }, [applyZoom]);

        const handlePointerDown = useCallback(
            (event: ReactPointerEvent<HTMLDivElement>) => {
                if (event.pointerType === "mouse" && event.button !== 0) {
                    return;
                }
                event.preventDefault();
                if (!containerRef.current) {
                    return;
                }
                containerRef.current.setPointerCapture(event.pointerId);
                panState.current = {
                    pointerId: event.pointerId,
                    startX: event.clientX,
                    startY: event.clientY,
                    originX: offset.x,
                    originY: offset.y,
                };
                setIsPanning(true);
            },
            [offset],
        );

        const handlePointerMove = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
            const state = panState.current;
            if (!state || state.pointerId !== event.pointerId) {
                return;
            }
            event.preventDefault();
            const dx = event.clientX - state.startX;
            const dy = event.clientY - state.startY;
            setOffsetState({
                x: state.originX + dx,
                y: state.originY + dy,
            });
        }, []);

        const endPan = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
            if (panState.current?.pointerId === event.pointerId) {
                containerRef.current?.releasePointerCapture(event.pointerId);
                panState.current = null;
                setIsPanning(false);
            }
        }, []);

        useImperativeHandle(
            ref,
            () => ({
                setZoom: (value: number) => {
                    const container = containerRef.current;
                    if (!container) {
                        return;
                    }
                    const rect = container.getBoundingClientRect();
                    applyZoom(value, { x: rect.width / 2, y: rect.height / 2 });
                },
                resetView: () => {
                    if (!fitState.current) {
                        updateFitState();
                    } else {
                        setZoomState(fitState.current.zoom);
                        setOffsetState(fitState.current.offset);
                        setContentOrigin(fitState.current.origin);
                        panState.current = null;
                        setIsPanning(false);
                        onStateChange?.({ zoom: fitState.current.zoom });
                    }
                },
            }),
            [applyZoom, onStateChange, updateFitState],
        );

        return (
            <div
                ref={containerRef}
                className="uml-svg"
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={endPan}
                onPointerLeave={endPan}
                style={{ cursor: isPanning ? "grabbing" : "grab" }}
            >
                <div
                    className="uml-svg-inner"
                    style={{
                        transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom}) translate(${-contentOrigin.x}px, ${-contentOrigin.y}px)`,
                        transformOrigin: "top left",
                    }}
                    dangerouslySetInnerHTML={content}
                />
            </div>
        );
    },
);

function parseSvgDimension(raw: string | null): number | null {
    if (!raw) {
        return null;
    }
    const match = raw.trim().match(/^([0-9]+(?:\.[0-9]+)?)\s*(pt|px)?$/i);
    if (!match) {
        return null;
    }
    const value = parseFloat(match[1]);
    const unit = match[2]?.toLowerCase();
    if (!Number.isFinite(value)) {
        return null;
    }
    if (unit === "pt") {
        return value * (96 / 72);
    }
    return value;
}

interface UmlCanvasProps {
    isLoading: boolean;
    isError: boolean;
    error: unknown;
    classCount: number;
    svgMarkup: string | null;
    svgHandleRef: React.RefObject<UmlSvgHandle>;
    onCanvasStateChange: (state: UmlViewState) => void;
    selectedClassId: string | null;
    onNodeClick: (classId: string) => void;
    selectedClass: UMLClass | null | undefined;
    onCloseDetails: () => void;
}

export function UmlCanvas({
    isLoading,
    isError,
    error,
    classCount,
    svgMarkup,
    svgHandleRef,
    onCanvasStateChange,
    selectedClassId,
    onNodeClick,
    selectedClass,
    onCloseDetails,
}: UmlCanvasProps): JSX.Element {
    return (
        <section className="uml-canvas" aria-live="polite" aria-busy={isLoading}>
            {isLoading ? (
                <div className="uml-loading" role="status">
                    <div className="uml-spinner" aria-hidden="true"></div>
                    <p className="summary-info">Generating UML model…</p>
                </div>
            ) : isError ? (
                <p className="summary-error" role="alert">
                    Could not generate the model: {String(error)}
                </p>
            ) : classCount === 0 ? (
                <p className="summary-info">No classes match the selected filters.</p>
            ) : svgMarkup ? (
                <>
                    <UmlSvgContainer
                        ref={svgHandleRef}
                        svg={svgMarkup}
                        onStateChange={onCanvasStateChange}
                        onNodeClick={onNodeClick}
                        selectedNodeId={selectedClassId}
                    />
                    {selectedClass && (
                        <ClassDetailsPanel classInfo={selectedClass} onClose={onCloseDetails} />
                    )}
                </>
            ) : (
                <p className="summary-info">The backend did not return a valid diagram.</p>
            )}
        </section>
    );
}
