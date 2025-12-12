import type { UMLClass } from "../../api/types";

interface UmlSearchProps {
    searchTerm: string;
    onSearchChange: (value: string) => void;
    filteredClasses: UMLClass[];
    onSelectClass: (classId: string) => void;
}

export function UmlSearch({
    searchTerm,
    onSearchChange,
    filteredClasses,
    onSelectClass,
}: UmlSearchProps): JSX.Element {
    return (
        <section className="uml-search-section" aria-label="Class search">
            <div className="uml-search-container">
                <label htmlFor="uml-search" className="sr-only">
                    Search class
                </label>
                <input
                    id="uml-search"
                    type="text"
                    className="uml-search-input"
                    placeholder="Search class by name, module, or file..."
                    value={searchTerm}
                    onChange={(e) => onSearchChange(e.target.value)}
                    aria-label="Search class by name, module, or file"
                    aria-autocomplete="list"
                    aria-controls={filteredClasses.length > 0 ? "uml-search-results" : undefined}
                    aria-expanded={filteredClasses.length > 0}
                />
                {filteredClasses.length > 0 && (
                    <div id="uml-search-results" className="uml-search-results" role="listbox">
                        {filteredClasses.slice(0, 10).map((cls) => (
                            <button
                                key={cls.id}
                                type="button"
                                className="uml-search-result-item"
                                onClick={() => onSelectClass(cls.id)}
                                role="option"
                                aria-label={`Select class ${cls.name} from module ${cls.module}`}
                            >
                                <div className="search-result-name">{cls.name}</div>
                                <div className="search-result-path">{cls.module}</div>
                            </button>
                        ))}
                        {filteredClasses.length > 10 && (
                            <div className="uml-search-more">+{filteredClasses.length - 10} more results</div>
                        )}
                    </div>
                )}
            </div>
        </section>
    );
}
