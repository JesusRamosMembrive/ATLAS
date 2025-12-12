#pragma once

#include "models/clone_types.hpp"
#include "core/hash_index.hpp"
#include <vector>


namespace aegis::similarity {

/**
 * Extends clone regions to detect Type-3 clones.
 *
 * Type-3 clones are code fragments that are similar but have
 * modifications such as added/removed lines or statements.
 * This class extends seed matches (Type-1/2) to find larger
 * similar regions with gaps.
 */
class CloneExtender {
public:
    /**
     * Configuration for clone extension.
     */
    struct Config {
        // Maximum gap (in tokens) allowed when extending
        size_t max_gap;

        // Minimum similarity threshold (Jaccard coefficient)
        float min_similarity;

        // Minimum tokens after extension
        size_t min_tokens;

        // Maximum tokens to look ahead when extending
        size_t lookahead;

        // Default constructor with default values
        Config()
            : max_gap(5)
            , min_similarity(0.7f)
            , min_tokens(30)
            , lookahead(10)
        {}
    };

    explicit CloneExtender(const Config& config = Config());

    /**
     * Extend a clone pair to find the maximum similar region.
     *
     * Starting from a seed match, extends forward and backward
     * while maintaining similarity above a threshold.
     *
     * @param pair The seed clone pair
     * @param file_a Tokenized source of location A
     * @param file_b Tokenized source of location B
     * @return Extended clone pair (maybe same if no extension possible)
     */
    [[nodiscard]] ClonePair extend(
        const ClonePair& pair,
        const TokenizedFile& file_a,
        const TokenizedFile& file_b
    ) const;

    /**
     * Calculate Jaccard similarity between two token sequences.
     *
     * Jaccard = |intersection| / |union|
     * Uses normalized hashes for comparison.
     *
     * @param tokens_a First token sequence
     * @param start_a Start index in tokens_a
     * @param count_a Number of tokens from tokens_a
     * @param tokens_b Second token sequence
     * @param start_b Start index in tokens_b
     * @param count_b Number of tokens from tokens_b
     * @return Similarity score 0.0 to 1.0
     */
    static float jaccard_similarity(
        const std::vector<NormalizedToken>& tokens_a,
        size_t start_a, size_t count_a,
        const std::vector<NormalizedToken>& tokens_b,
        size_t start_b, size_t count_b
    );

    /**
     * Calculate token-level alignment similarity.
     *
     * Compares tokens position-by-position, accounting for gaps.
     * More precise than Jaccard for structured code.
     *
     * @return Similarity score 0.0 to 1.0
     */
    static float alignment_similarity(
        const std::vector<NormalizedToken>& tokens_a,
        size_t start_a, size_t count_a,
        const std::vector<NormalizedToken>& tokens_b,
        size_t start_b, size_t count_b,
        size_t max_gap = 5
    );

    /**
     * Process a batch of clone pairs and extend them.
     *
     * @param pairs Clone pairs to extend
     * @param files Map of file_id -> TokenizedFile
     * @param index
     * @return Extended clone pairs, potentially merged
     */
    [[nodiscard]] std::vector<ClonePair> extend_all(
        const std::vector<ClonePair>& pairs,
        const std::vector<TokenizedFile>& files,
        const HashIndex& index
    ) const;

private:
    Config config_;

    // Extend forward from the current position
    [[nodiscard]] size_t extend_forward(
        const std::vector<NormalizedToken>& tokens_a, size_t pos_a,
        const std::vector<NormalizedToken>& tokens_b, size_t pos_b
    ) const;

    // Extend backward from the current position
    [[nodiscard]] size_t extend_backward(
        const std::vector<NormalizedToken>& tokens_a, size_t pos_a,
        const std::vector<NormalizedToken>& tokens_b, size_t pos_b
    ) const;
};

}  // namespace aegis::similarity
