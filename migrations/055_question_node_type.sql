-- 055: Add 'question' node type for storing unanswered search queries
ALTER TYPE node_type ADD VALUE IF NOT EXISTS 'question';
