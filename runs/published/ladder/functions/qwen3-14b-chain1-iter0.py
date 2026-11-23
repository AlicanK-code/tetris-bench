def score(board, placement):
    # Helper function to calculate maximum height of filled columns
    def compute_max_height():
        max_h = 0
        for col in range(10):
            current_max = -1
            for row in range(20):
                if board[row][col]:
                    current_max = row
            if current_max > max_h:
                max_h = current_max
        return max_h

    # Helper function to count number of holes
    def compute_holes():
        holes = 0
        for col in range(10):
            lowest_filled_row = -1
            for row in range(19, -1, -1):
                if board[row][col]:
                    lowest_filled_row = row
                    break
            if lowest_filled_row == -1:
                continue
            for row in range(0, lowest_filled_row):
                if not board[row][col]:
                    holes += 1
        return holes

    # Helper function to calculate surface roughness
    def compute_roughness():
        roughness = 0
        column_heights = []
        for col in range(10):
            lowest_filled_row = -1
            for row in range(19, -1, -1):
                if board[row][col]:
                    lowest_filled_row = row
                    break
            if lowest_filled_row == -1:
                column_heights.append(0)
            else:
                column_heights.append(lowest_filled_row)
        for i in range(9):
            roughness += abs(column_heights[i] - column_heights[i + 1])
        return roughness

    # Calculate individual metrics
    lines_cleared = placement["lines_cleared"]
    max_h = compute_max_height()
    holes = compute_holes()
    roughness = compute_roughness()

    # Combine metrics into a score
    # Higher lines cleared is better, lower height, holes, and roughness are better
    return float(lines_cleared * 10 - max_h * 0.5 - holes * 1 - roughness * 0.2)
