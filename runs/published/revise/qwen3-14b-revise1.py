def score(board, placement):
    # Calculate column heights
    heights = [0] * 10
    for col in range(10):
        count = 0
        for row in range(20):
            if board[row][col]:
                count += 1
        heights[col] = count

    # Calculate max height
    max_height = max(heights)

    # Calculate number of holes
    holes = 0
    for col in range(10):
        for row in range(20):
            if not board[row][col] and heights[col] > row:
                holes += 1

    # Calculate bumpiness
    bumpiness = 0
    for i in range(9):
        bumpiness += abs(heights[i] - heights[i + 1])

    # Combine factors with weights
    lines_cleared = placement["lines_cleared"]
    return lines_cleared * 100 - max_height * 10 - holes * 5 - bumpiness * 2
