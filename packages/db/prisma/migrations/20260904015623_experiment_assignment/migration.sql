-- AlterTable
ALTER TABLE "content_pieces" ADD COLUMN     "experimentId" TEXT,
ADD COLUMN     "experimentVariant" TEXT;

-- CreateIndex
CREATE INDEX "content_pieces_experimentId_idx" ON "content_pieces"("experimentId");

-- AddForeignKey
ALTER TABLE "content_pieces" ADD CONSTRAINT "content_pieces_experimentId_fkey" FOREIGN KEY ("experimentId") REFERENCES "experiments"("id") ON DELETE SET NULL ON UPDATE CASCADE;
